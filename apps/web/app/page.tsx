"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  ActivityEntry,
  MemoryReport,
  MemoryRunResponse,
  UploadResponse,
  MemoryRunStatus
} from "@/types/memory";
import UploadForm from "@/components/UploadForm";
import ActivityFeed from "@/components/ActivityFeed";
import Corkboard from "@/components/Corkboard";
import MemoryReportPanel from "@/components/MemoryReportPanel";
import { fetchMemoryRun, getMemoryRunStreamUrl, getMemoryRunStreamUrlWithCursorAsync } from "@/lib/api-client";
import { startMemoryRunRealtime } from "@/lib/memory-run-realtime";
import { useAuth } from "@/lib/auth-context";
import { AUTH_ENABLED } from "@/lib/auth-mode";
import { ProtectedRoute } from "@/lib/protected-route";

const POLL_INTERVAL = 2000;

const statusLabels: Record<MemoryRunStatus, string> = {
  queued: "queued",
  detecting: "detecting",
  matching: "matching",
  synthesizing: "summarizing",
  done: "done",
  failed: "failed",
};

function HomeContent() {
  const router = useRouter();
  const { logout } = useAuth();
  
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [memory_runId, setMemoryRunId] = useState<string | null>(null);
  const [memory_run, setMemoryRun] = useState<MemoryRunResponse | null>(null);
  const [liveActivities, setLiveActivities] = useState<ActivityEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [realtimeMode, setRealtimeMode] = useState<"sse" | "polling">("sse");
  const [realtimeStatus, setRealtimeStatus] = useState<"connecting" | "live" | "fallback">("connecting");
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    if (!memory_runId) return;
    let active = true;
    const poll = async () => {
      try {
        const data = await fetchMemoryRun(memory_runId);
        if (active) setMemoryRun(data);
        setLastUpdatedAt(new Date().toISOString());
      } catch (err: any) {
        if (active) {
          // Handle 401 by logging out and redirecting
          if (err.status === 401) {
            logout();
            router.push("/login?message=Session+expired");
          } else {
            setError(err.message || "Failed to fetch memory result");
          }
        }
      }
    };
    poll();
    const interval = setInterval(poll, POLL_INTERVAL);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [memory_runId, logout, router]);

  useEffect(() => {
    setRealtimeStatus("connecting");
    const stop = startMemoryRunRealtime({
      streamUrl: getMemoryRunStreamUrl(),
      resolveStreamUrl: getMemoryRunStreamUrlWithCursorAsync,
      onUpdate: (update) => {
        if (update.memory_run_id === memory_runId) {
          void fetchMemoryRun(update.memory_run_id)
            .then((payload) => {
              setMemoryRun(payload);
              setLastUpdatedAt(new Date().toISOString());
            })
            .catch(() => {
              // Keep the current state until next successful poll/update.
            });
        }
        setRealtimeStatus("live");
      },
      onEvent: (eventType, payload) => {
        const detail = payload.payload && Object.keys(payload.payload).length > 0 ? JSON.stringify(payload.payload) : "Event received";
        const activity: ActivityEntry = {
          stage: eventType,
          message: detail,
          created_at: payload.timestamp || new Date().toISOString(),
        };
        setLiveActivities((prev) => [activity, ...prev].slice(0, 25));
        setLastUpdatedAt(payload.timestamp || new Date().toISOString());
      },
      onPollingTick: async () => {
        if (!memory_runId) {
          return;
        }
        const data = await fetchMemoryRun(memory_runId);
        setMemoryRun(data);
        setRealtimeStatus("fallback");
      },
      onModeChange: (mode) => {
        setRealtimeMode(mode);
        setRealtimeStatus(mode === "sse" ? "live" : "fallback");
      },
    });

    return () => stop();
  }, [memory_runId]);

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const status: MemoryRunStatus | null = memory_run ? memory_run.status : null;
  const activities: ActivityEntry[] = [...liveActivities, ...(memory_run?.activities || [])].slice(0, 50);
  const memory_report: MemoryReport | undefined = memory_run?.memory_report as MemoryReport | undefined;
  const lastUpdatedLabel = lastUpdatedAt ? new Date(lastUpdatedAt).toLocaleTimeString() : "–";
  const currentMemoryRunLabel = memory_runId ? `Active: ${memory_runId}` : "Idle";
  const finalVerdict = useMemo(() => {
    const summary = (memory_report?.recognition_summary || {}) as Record<string, unknown>;
    const trace = (memory_report?.decision_trace || {}) as Record<string, unknown>;
    const decision = String(
      summary.final_verdict_decision ?? summary.recognition_decision ?? trace.final_verdict_decision ?? "pending"
    );
    const name = String(
      summary.final_verdict_name ?? trace.final_verdict_name ?? "Unknown"
    );
    return {
      name,
      decision,
      hasResult: Boolean(memory_report && memory_run?.status === "done"),
      isUnknown: name.trim().toLowerCase() === "unknown",
    };
  }, [memory_report, memory_run?.status]);

  return (
    <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      <header className="card p-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm text-gray-400">Local-first personal memory</p>
          <h1 className="text-3xl font-bold">Self-Learning Vision</h1>
          <p className="text-sm text-gray-500">Upload a photo, pick a face, and recall who they are from your local memory.</p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <span className="badge">Private & Local</span>
          <span className="badge">No external lookup by default</span>
          <button
            onClick={() => router.push("/memory-runs")}
            className="px-3 py-1.5 text-sm font-medium rounded-md bg-white/10 text-gray-100 hover:bg-white/20 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-board-accent"
          >
            Open Memory Runs
          </button>
          {AUTH_ENABLED && (
            <button
              onClick={handleLogout}
              className="px-3 py-1.5 text-sm font-medium rounded-md bg-gray-200 text-gray-800 hover:bg-gray-300 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-black"
            >
              Logout
            </button>
          )}
        </div>
      </header>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-2 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3" aria-label="Memory status overview">
            <div className="card p-3">
              <p className="text-xs uppercase tracking-wide text-gray-400">Updates</p>
              <div className="flex items-center justify-between">
                <p className="text-lg font-semibold">{realtimeMode === "sse" ? "Live" : "Polling"}</p>
                <span className={`badge ${realtimeStatus === "live" ? "bg-emerald-700 text-white" : "bg-amber-600/70 text-white"}`}>
                  {realtimeStatus === "live" ? "Healthy" : realtimeStatus === "connecting" ? "Connecting" : "Fallback"}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1">Keeps memory results fresh while you work.</p>
            </div>
            <div className="card p-3">
              <p className="text-xs uppercase tracking-wide text-gray-400">Memory Run</p>
              <div className="flex items-center justify-between gap-2">
                <p className="text-lg font-semibold break-all">{currentMemoryRunLabel}</p>
                <span className="badge bg-white/10 text-gray-100 capitalize">
                  {finalVerdict.hasResult ? finalVerdict.decision : status ? statusLabels[status] : "pending"}
                </span>
              </div>
              <p className="text-sm text-gray-200 mt-1" aria-live="polite">
                Memory result: {finalVerdict.hasResult ? finalVerdict.name : "Processing"}
              </p>
              {finalVerdict.hasResult && finalVerdict.isUnknown && (
                <p className="text-xs text-amber-200 mt-1">Unknown (no trusted match)</p>
              )}
              <p className="text-xs text-gray-500 mt-1">Last update: {lastUpdatedLabel}</p>
            </div>
            <div className="card p-3">
              <p className="text-xs uppercase tracking-wide text-gray-400">Upload</p>
              <p className="text-lg font-semibold">{upload ? "File ready" : "Waiting for upload"}</p>
              <p className="text-xs text-gray-500 mt-1">Detected faces and memory notes stay local.</p>
            </div>
          </div>

          {error && <div className="card p-3 text-red-400" role="alert">{error}</div>}

          <UploadForm
            onMemoryRunStart={(id) => {
              setMemoryRunId(id);
              setMemoryRun(null);
              setLiveActivities([]);
              setError(null);
            }}
            onUploadComplete={(payload) => setUpload(payload)}
          />

          <Corkboard memory_report={memory_report} />
        </div>

        <div className="space-y-4">
          <ActivityFeed activities={activities} status={status} mode={realtimeMode} />
          <MemoryReportPanel memory_report={memory_report} />
        </div>
      </section>

      <footer className="text-xs text-gray-500 space-y-1">
        <p>Default runs complete with local recognition on this machine.</p>
        <p>Polling every 2 seconds when a run is active. Everything stays on this machine.</p>
      </footer>
    </main>
  );
}

export default function HomePage() {
  return (
    <ProtectedRoute>
      <HomeContent />
    </ProtectedRoute>
  );
}


