import { describe, expect, it } from "vitest";
import { filterMemoryRuns } from "@/lib/memory-run-history";
import type { MemoryRunHistoryItem } from "@/types/memory";

const fixedNow = new Date("2026-03-29T12:00:00.000Z");

const items: MemoryRunHistoryItem[] = [
  {
    memory_run_id: "1",
    status: "queued",
    created_at: "2026-03-29T11:30:00.000Z",
    last_updated: "2026-03-29T11:31:00.000Z",
  },
  {
    memory_run_id: "2",
    status: "failed",
    created_at: "2026-03-25T12:00:00.000Z",
    last_updated: "2026-03-25T12:30:00.000Z",
  },
  {
    memory_run_id: "3",
    status: "done",
    created_at: "2026-01-20T09:00:00.000Z",
    last_updated: "2026-01-20T10:00:00.000Z",
  },
];

describe("filterMemoryRuns", () => {
  it("filters by status", () => {
    const result = filterMemoryRuns(items, "failed", "all", fixedNow);
    expect(result).toHaveLength(1);
    expect(result[0].memory_run_id).toBe("2");
  });

  it("filters by date range", () => {
    const result = filterMemoryRuns(items, "all", "7d", fixedNow);
    expect(result.map((item) => item.memory_run_id)).toEqual(["1", "2"]);
  });

  it("applies status and date filters together", () => {
    const result = filterMemoryRuns(items, "done", "7d", fixedNow);
    expect(result).toHaveLength(0);
  });
});

