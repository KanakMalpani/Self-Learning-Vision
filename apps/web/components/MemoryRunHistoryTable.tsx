"use client";

import React from "react";
import type { MemoryRunHistoryItem } from "@/types/memory";

interface MemoryRunHistoryTableProps {
  memory_runs: MemoryRunHistoryItem[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onOpenMemoryRun: (memory_runId: string) => void;
}

function formatDate(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString();
}

function statusClass(status: MemoryRunHistoryItem["status"]): string {
  if (status === "done") return "bg-emerald-500/20 text-emerald-200 border-emerald-300/30";
  if (status === "failed") return "bg-red-500/20 text-red-200 border-red-300/30";
  if (status === "queued") return "bg-slate-500/20 text-slate-100 border-slate-300/30";
  return "bg-sky-500/20 text-sky-100 border-sky-300/30";
}

function statusLabel(status: MemoryRunHistoryItem["status"]): string {
  if (status === "synthesizing") return "summarizing";
  return status;
}

async function copyId(value: string) {
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
    }
  } catch {
    // Non-blocking best-effort copy.
  }
}

export default function MemoryRunHistoryTable({
  memory_runs,
  loading,
  error,
  onRetry,
  onOpenMemoryRun,
}: MemoryRunHistoryTableProps) {
  if (loading) {
    return (
      <div className="card p-6">
        <p className="text-sm text-gray-300">Loading memory runs...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card p-6 space-y-3">
        <p className="text-sm text-red-300">{error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="px-3 py-2 text-sm rounded-md bg-red-500/20 hover:bg-red-500/30 text-red-100 border border-red-300/30"
        >
          Retry
        </button>
      </div>
    );
  }

  if (memory_runs.length === 0) {
    return (
      <div className="card p-6">
        <p className="text-sm text-gray-300">No memory runs found for the current filters.</p>
      </div>
    );
  }

  return (
    <div className="card overflow-x-auto" role="region" aria-label="Memory run list">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left border-b border-white/10 text-gray-300">
            <th className="px-4 py-3 font-semibold">Run ID</th>
            <th className="px-4 py-3 font-semibold">Status</th>
            <th className="px-4 py-3 font-semibold">Created At</th>
            <th className="px-4 py-3 font-semibold">Last Updated</th>
            <th className="px-4 py-3 font-semibold">Action</th>
          </tr>
        </thead>
        <tbody>
          {memory_runs.map((item) => (
            <tr
              key={item.memory_run_id}
              className="border-b border-white/5 last:border-b-0 cursor-pointer hover:bg-white/5"
              onClick={() => onOpenMemoryRun(item.memory_run_id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onOpenMemoryRun(item.memory_run_id);
                }
              }}
              tabIndex={0}
              aria-label={`Open memory run ${item.memory_run_id}`}
            >
              <td className="px-4 py-3 font-mono text-xs break-all text-gray-200">{item.memory_run_id}</td>
              <td className="px-4 py-3">
                <span className={`inline-flex rounded-full border px-2 py-1 text-xs uppercase tracking-wide ${statusClass(item.status)}`}>
                  {statusLabel(item.status)}
                </span>
              </td>
              <td className="px-4 py-3 text-gray-200">{formatDate(item.created_at)}</td>
              <td className="px-4 py-3 text-gray-200">{formatDate(item.last_updated)}</td>
              <td className="px-4 py-3">
                <button
                  type="button"
                  className="px-2 py-1 mr-2 text-xs rounded-md bg-white/10 hover:bg-white/20 text-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-board-accent"
                  onClick={(event) => {
                    event.stopPropagation();
                    onOpenMemoryRun(item.memory_run_id);
                  }}
                >
                  Open
                </button>
                <button
                  type="button"
                  className="px-2 py-1 text-xs rounded-md border border-white/15 text-gray-100 hover:border-board-accent/70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-board-accent"
                  onClick={(event) => {
                    event.stopPropagation();
                    void copyId(item.memory_run_id);
                  }}
                  aria-label={`Copy memory run id ${item.memory_run_id}`}
                >
                  Copy ID
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

