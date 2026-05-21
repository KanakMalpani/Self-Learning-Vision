"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import MemoryReportPanel from "@/components/MemoryReportPanel";
import ActivityFeed from "@/components/ActivityFeed";
import { fetchMemoryRun } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { ProtectedRoute } from "@/lib/protected-route";
import type { MemoryRunResponse } from "@/types/memory";

function MemoryRunDetailContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { logout } = useAuth();
  const memory_runId = searchParams.get("id");

  const [detail, setDetail] = useState<MemoryRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    if (!memory_runId) {
      setError("Missing memory run id");
      setLoading(false);
      return;
    }

    setLoading(true);
    fetchMemoryRun(memory_runId)
      .then((payload) => {
        if (!active) return;
        setDetail(payload);
        setError(null);
      })
      .catch((err: any) => {
        if (!active) return;
        if (err.status === 401) {
          logout();
          router.push("/login?message=Session+expired");
          return;
        }
        setError(err.message || "Failed to load memory run");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [memory_runId, logout, router]);

  const resultName = useMemo(() => {
    const summary = detail?.memory_report?.recognition_summary as Record<string, unknown> | undefined;
    return String(summary?.final_verdict_name ?? detail?.memory_report?.subject?.name_or_alias ?? "Unknown");
  }, [detail]);

  return (
    <main className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      <header className="card p-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm text-gray-400">Memory run</p>
          <h1 className="text-3xl font-bold break-all">{resultName}</h1>
          <p className="text-xs text-gray-500 break-all">{memory_runId}</p>
        </div>
        <div className="flex gap-2">
          <Link className="px-3 py-1.5 rounded-md bg-white/10 text-sm text-gray-100" href="/memory-runs">
            Memory Runs
          </Link>
          <Link className="px-3 py-1.5 rounded-md bg-board-accent text-sm font-semibold text-black" href="/">
            New Upload
          </Link>
        </div>
      </header>

      {loading && <div className="card p-4 text-sm text-gray-300">Loading memory run...</div>}
      {error && <div className="card p-4 text-sm text-red-300" role="alert">{error}</div>}

      {detail && (
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <MemoryReportPanel memory_report={detail.memory_report ?? undefined} />
          </div>
          <ActivityFeed activities={detail.activities} status={detail.status} mode="polling" />
        </section>
      )}
    </main>
  );
}

export default function MemoryRunDetailPage() {
  return (
    <ProtectedRoute>
      <MemoryRunDetailContent />
    </ProtectedRoute>
  );
}
