import type { MemoryRunHistoryItem, MemoryRunStatus } from "@/types/memory";

export type StatusFilter = "all" | MemoryRunStatus;
export type DateRangeFilter = "24h" | "7d" | "30d" | "all";

function toDate(value?: string | null): Date | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
}

function rangeStart(range: DateRangeFilter, now: Date): Date | null {
  if (range === "all") return null;
  const offsetMs =
    range === "24h"
      ? 24 * 60 * 60 * 1000
      : range === "7d"
      ? 7 * 24 * 60 * 60 * 1000
      : 30 * 24 * 60 * 60 * 1000;
  return new Date(now.getTime() - offsetMs);
}

export function filterMemoryRuns(
  items: MemoryRunHistoryItem[],
  status: StatusFilter,
  dateRange: DateRangeFilter,
  now: Date = new Date()
): MemoryRunHistoryItem[] {
  const start = rangeStart(dateRange, now);

  return items.filter((item) => {
    if (status !== "all" && item.status !== status) {
      return false;
    }

    if (!start) {
      return true;
    }

    const createdAt = toDate(item.created_at);
    if (!createdAt) {
      return false;
    }

    return createdAt >= start;
  });
}

