"use client";

import React from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import MemoryRunHistoryTable from "@/components/MemoryRunHistoryTable";
import {
  fetchMemoryRunHistory,
  getMemoryRunStreamUrl,
  ApiError,
} from "@/lib/api-client";
import {
  DateRangeFilter,
  filterMemoryRuns,
  StatusFilter,
} from "@/lib/memory-run-history";
import { startMemoryRunRealtime } from "@/lib/memory-run-realtime";
import { useAuth } from "@/lib/auth-context";
import { AUTH_ENABLED } from "@/lib/auth-mode";
import { ProtectedRoute } from "@/lib/protected-route";
import type { MemoryRunHistoryItem } from "@/types/memory";

function mergeMemoryRunUpdate(
  current: MemoryRunHistoryItem[],
  update: MemoryRunHistoryItem
): MemoryRunHistoryItem[] {
  const existing = current.find((item) => item.memory_run_id === update.memory_run_id);
  if (!existing) {
    return [update, ...current].sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  }

  return current.map((item) =>
    item.memory_run_id === update.memory_run_id
      ? {
          ...item,
          status: update.status,
          last_updated: update.last_updated || item.last_updated,
          created_at: update.created_at || item.created_at,
        }
      : item
  );
}

function MemoryRunsContent() {
  const router = useRouter();
  const { logout } = useAuth();

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [dateRangeFilter, setDateRangeFilter] = useState<DateRangeFilter>("7d");
  const [items, setItems] = useState<MemoryRunHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [realtimeError, setRealtimeError] = useState<string | null>(null);
  const [realtimeMode, setRealtimeMode] = useState<"sse" | "polling">("sse");
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem("memory-run-filters");
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as { statusFilter?: StatusFilter; dateRangeFilter?: DateRangeFilter };
        if (parsed.statusFilter) setStatusFilter(parsed.statusFilter);
        if (parsed.dateRangeFilter) setDateRangeFilter(parsed.dateRangeFilter);
      } catch {
        // ignore invalid cache
      }
    }
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      setFetchError(null);
      const response = await fetchMemoryRunHistory();
      setItems(response.memory_runs);
      setLastUpdated(new Date().toISOString());
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        if (AUTH_ENABLED) {
          logout();
          router.push("/login?message=Session+expired");
        } else {
          setFetchError("Unauthorized request");
        }
        return;
      }
      const message = err instanceof Error ? err.message : "Failed to load memory runs";
      setFetchError(`${message}. You can retry now.`);
    } finally {
      setLoading(false);
    }
  }, [logout, router]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(
      "memory-run-filters",
      JSON.stringify({ statusFilter, dateRangeFilter })
    );
  }, [statusFilter, dateRangeFilter]);

  useEffect(() => {
    const stop = startMemoryRunRealtime({
      streamUrl: getMemoryRunStreamUrl(),
      onUpdate: (update) => {
        setItems((current) => mergeMemoryRunUpdate(current, update));
        setLastUpdated(new Date().toISOString());
      },
      onPollingTick: async () => {
        try {
          const response = await fetchMemoryRunHistory();
          setItems(response.memory_runs);
          setRealtimeError(null);
          setLastUpdated(new Date().toISOString());
        } catch (err) {
          if (err instanceof ApiError && err.status === 401) {
            if (AUTH_ENABLED) {
              logout();
              router.push("/login?message=Session+expired");
            } else {
              setRealtimeError("Unauthorized request");
            }
            return;
          }
          setRealtimeError("Realtime updates are temporarily unavailable. Retry to refresh.");
        }
      },
      onModeChange: setRealtimeMode,
    });

    return () => {
      stop();
    };
  }, [logout, router]);

  const filteredItems = useMemo(
    () => filterMemoryRuns(items, statusFilter, dateRangeFilter),
    [items, statusFilter, dateRangeFilter]
  );

  return (
    <main className="max-w-6xl mx-auto px-4 py-8 space-y-5">
      <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div className="space-y-1">
          <nav aria-label="Breadcrumb" className="text-xs text-gray-400">
            <ol className="flex items-center gap-1">
              <li className="text-gray-500">Home</li>
              <li aria-hidden className="text-gray-600">/</li>
              <li className="text-gray-200 font-semibold">Memory Runs</li>
            </ol>
          </nav>
          <p className="text-sm text-gray-400">Recognition history and local memory updates</p>
          <h1 className="text-3xl font-bold">Memory Runs</h1>
          <p className="text-xs text-gray-500">Filters stick while you browse. Last updated {lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : "–"}.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="badge">{realtimeMode === "sse" ? "Live: SSE" : "Live: Polling Fallback"}</span>
          <button
            type="button"
            onClick={() => router.push("/")}
            className="px-3 py-2 rounded-md text-sm bg-white/10 hover:bg-white/20 text-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-board-accent"
          >
            Back to Remember
          </button>
        </div>
      </header>

      <section className="card p-4 flex flex-col md:flex-row gap-3 md:items-end" aria-label="Memory run filters">
        <div className="flex flex-col gap-1">
          <label htmlFor="status-filter" className="text-xs uppercase tracking-wide text-gray-400">
            Status
          </label>
          <select
            id="status-filter"
            className="bg-black/30 border border-white/15 rounded-md px-3 py-2 text-sm"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
          >
            <option value="all">All</option>
            <option value="queued">Queued</option>
            <option value="detecting">Detecting</option>
            <option value="matching">Matching</option>
            <option value="synthesizing">Summarizing</option>
            <option value="done">Done</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="date-range" className="text-xs uppercase tracking-wide text-gray-400">
            Date Range
          </label>
          <select
            id="date-range"
            className="bg-black/30 border border-white/15 rounded-md px-3 py-2 text-sm"
            value={dateRangeFilter}
            onChange={(event) => setDateRangeFilter(event.target.value as DateRangeFilter)}
          >
            <option value="24h">Last 24h</option>
            <option value="7d">Last 7d</option>
            <option value="30d">Last 30d</option>
            <option value="all">All time</option>
          </select>
        </div>

        <button
          type="button"
          onClick={() => {
            setLoading(true);
            void loadHistory();
          }}
          className="px-3 py-2 rounded-md text-sm bg-board-accent text-black hover:opacity-90"
        >
          Refresh
        </button>
      </section>

      {realtimeError && (
        <div className="card p-3 text-sm text-red-300 border border-red-400/25" role="alert">
          {realtimeError}
        </div>
      )}

      <MemoryRunHistoryTable
        memory_runs={filteredItems}
        loading={loading}
        error={fetchError}
        onOpenMemoryRun={(memory_runId) => {
          router.push(`/memory-runs/detail?id=${encodeURIComponent(memory_runId)}`);
        }}
        onRetry={() => {
          setLoading(true);
          void loadHistory();
        }}
      />
    </main>
  );
}

export default function MemoryRunsPage() {
  return (
    <ProtectedRoute>
      <MemoryRunsContent />
    </ProtectedRoute>
  );
}

