"use client";

import React from "react";
import type { ActivityEntry, MemoryRunStatus } from "@/types/memory";
import { formatDistanceToNow } from "date-fns";

const statusColor: Record<MemoryRunStatus | "", string> = {
  queued: "bg-slate-700",
  detecting: "bg-purple-700",
  matching: "bg-blue-700",
  synthesizing: "bg-indigo-700",
  done: "bg-green-700",
  failed: "bg-red-700",
  "": "bg-gray-700",
};

const stageStyle: Record<string, string> = {
  done: "bg-emerald-500/10 text-emerald-100 border-emerald-400/30",
  uploaded: "bg-blue-500/10 text-blue-100 border-blue-400/30",
  detected: "bg-indigo-500/10 text-indigo-100 border-indigo-400/30",
  recognized: "bg-cyan-500/10 text-cyan-100 border-cyan-400/30",
  enrolled: "bg-amber-500/10 text-amber-100 border-amber-400/30",
  memory_run_status: "bg-slate-500/10 text-slate-100 border-slate-400/30",
};

const stageLabels: Record<string, string> = {
  done: "Memory run complete",
  uploaded: "Photo uploaded",
  detected: "Faces detected",
  recognized: "Recognition complete",
  enrolled: "Identity saved",
  memory_run_status: "Memory run status",
};

const statusLabels: Record<MemoryRunStatus, string> = {
  queued: "queued",
  detecting: "detecting",
  matching: "matching",
  synthesizing: "summarizing",
  done: "done",
  failed: "failed",
};

function formatStage(stage: string): string {
  if (stageLabels[stage]) return stageLabels[stage];
  const pretty = stage.replace(/_/g, " ");
  return pretty.charAt(0).toUpperCase() + pretty.slice(1);
}

interface Props {
  activities: ActivityEntry[];
  status: MemoryRunStatus | null;
  mode?: "sse" | "polling";
}

export default function ActivityFeed({ activities, status, mode }: Props) {
  const statusBadge = status ? statusColor[status] : statusColor[""];
  return (
    <div className="card p-4 space-y-3 h-full">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-semibold">Activity</p>
          <p className="text-xs text-gray-500">Recent local memory events</p>
        </div>
        <div className="flex items-center gap-2">
          {mode && (
            <span className="badge bg-white/15 text-gray-100" aria-label={`Update mode: ${mode}`}>
              {mode === "sse" ? "Live" : "Polling"}
            </span>
          )}
          <span className={`badge ${statusBadge} text-white`}>{status ? statusLabels[status] : "idle"}</span>
        </div>
      </div>

      <div className="space-y-2 overflow-y-auto max-h-72 pr-1" role="list" aria-live="polite">
        {activities.length === 0 && <p className="text-sm text-gray-500">Waiting for a memory run.</p>}
        {activities.map((activity, idx) => {
          const tone = stageStyle[activity.stage] || "bg-white/5 text-gray-100 border-white/10";
          return (
            <div key={`${activity.created_at}-${idx}`} className={`rounded-lg px-3 py-2 border ${tone}`} role="listitem">
              <div className="text-xs text-gray-300 flex justify-between gap-3">
                <span className="font-semibold tracking-wide uppercase text-[11px]">{formatStage(activity.stage)}</span>
                <span>{formatDistanceToNow(new Date(activity.created_at), { addSuffix: true })}</span>
              </div>
              <p className="text-sm mt-1 leading-snug text-gray-50 break-words">{activity.message}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
