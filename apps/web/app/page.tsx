"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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
import { readApiFailure } from "@/lib/api-error";
import { fetchMemoryRun, getMemoryRunStreamUrlWithCursor } from "@/lib/api-client";
import { startMemoryRunRealtime } from "@/lib/memory-run-realtime";
import { useAuth } from "@/lib/auth-context";
import { AUTH_ENABLED } from "@/lib/auth-mode";
import { ProtectedRoute } from "@/lib/protected-route";

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

  const refreshMemoryRun = useCallback(
    async (runId: string) => {
      try {
        const data = await fetchMemoryRun(runId);
        setMemoryRun(data);
        setLastUpdatedAt(new Date().toISOString());
      } catch (error: unknown) {
        const failure = readApiFailure(error, "Failed to fetch memory result");
        if (failure.status === 401) {
          logout();
          router.push("/login?message=Session+expired");
          return;
        }
        setError(failure.message);
      }
    },
    [logout, router]
  );

  useEffect(() => {
    if (!memory_runId) return;
    void refreshMemoryRun(memory_runId);
  }, [memory_runId, refreshMemoryRun]);

  useEffect(() => {
    setRealtimeStatus("connecting");
    const stop = startMemoryRunRealtime({
      resolveStreamUrl: getMemoryRunStreamUrlWithCursor,
      onUpdate: (update) => {
        if (update.memory_run_id === memory_runId) {
          void refreshMemoryRun(update.memory_run_id);
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
        await refreshMemoryRun(memory_runId);
        setRealtimeStatus("fallback");
      },
      onModeChange: (mode) => {
        setRealtimeMode(mode);
        setRealtimeStatus(mode === "sse" ? "live" : "fallback");
      },
    });

    return () => stop();
  }, [memory_runId, refreshMemoryRun]);

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
    <main className="page space-y-8">
      <header className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <p className="kicker">Local memory</p>
          <h1 className="text-5xl leading-none">Remember a face</h1>
          <p className="lead">Upload a photo, pick a face, and match it against the people stored on this machine.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="badge">Private</span>
          <span className="badge">No web lookup</span>
          <button
            onClick={() => router.push("/memory-runs")}
            className="btn btn-quiet"
          >
            Open memory runs
          </button>
          {AUTH_ENABLED && (
            <button
              onClick={handleLogout}
              className="btn btn-quiet"
            >
              Logout
            </button>
          )}
        </div>
      </header>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-2 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3" aria-label="Memory status overview">
            <div className="card p-4">
              <p className="kicker">Updates</p>
              <div className="flex items-center justify-between">
                <p className="text-lg font-semibold">{memory_runId ? (realtimeMode === "sse" ? "Live" : "Polling") : "Idle"}</p>
                <span className="badge">
                  {!memory_runId
                    ? "Ready"
                    : realtimeStatus === "live"
                      ? "Healthy"
                      : realtimeStatus === "connecting"
                        ? "Connecting"
                        : "Fallback"}
                </span>
              </div>
              <p className="mt-2 text-sm text-[var(--muted)]">Keeps memory results fresh while you work.</p>
            </div>
            <div className="card p-4">
              <p className="kicker">Memory run</p>
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
              <p className="mt-2 text-sm text-[var(--muted)]">Last update: {lastUpdatedLabel}</p>
            </div>
            <div className="card p-4">
              <p className="kicker">Upload</p>
              <p className="text-lg font-semibold">{upload ? "File ready" : "Waiting for upload"}</p>
              <p className="mt-2 text-sm text-[var(--muted)]">Detected faces and memory notes stay local.</p>
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

      <footer className="space-y-1 text-sm text-[var(--muted)]">
        <p>Default runs complete with local recognition on this machine.</p>
        <p>
          {realtimeMode === "sse"
            ? "Live updates while a run is active. Everything stays on this machine."
            : "Checking for updates every few seconds while a run is active. Everything stays on this machine."}
        </p>
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


