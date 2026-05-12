"use client";

import { useEffect, useState } from "react";
import type { BenchmarkPackResponse, BenchmarkRunItem } from "@/types/memory";
import { createBenchmarkRun, fetchBenchmarkPack, fetchBenchmarkRuns } from "@/lib/api-client";

function metricLabel(value: unknown): string {
  if (value === null || value === undefined) return "n/a";
  if (typeof value === "number") return `${Math.round(value * 1000) / 10}%`;
  return String(value);
}

export default function BenchmarkHistoryPanel() {
  const [pack, setPack] = useState<BenchmarkPackResponse | null>(null);
  const [runs, setRuns] = useState<BenchmarkRunItem[]>([]);
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    async function load() {
      const [nextPack, history] = await Promise.all([fetchBenchmarkPack(), fetchBenchmarkRuns()]);
      setPack(nextPack);
      setRuns(history.runs);
    }
    void load();
  }, []);

  async function handleSnapshot() {
    const run = await createBenchmarkRun({
      label,
      notes: notes || null,
      benchmark_case_ids: pack?.cases.map((item) => item.case_id) || [],
    });
    setRuns((current) => [run, ...current]);
    setLabel("");
    setNotes("");
    setStatus("Benchmark snapshot saved.");
  }

  return (
    <section className="card p-5 space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-400">Benchmarking</p>
          <h2 className="text-xl font-semibold">Results History</h2>
          <p className="mt-1 text-sm text-gray-500">
            Save local metric snapshots before and after provider or threshold changes.
          </p>
        </div>
        <span className="badge">{pack?.case_count || 0} cases</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-3">
        <input
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          className="rounded-md border border-white/10 bg-black/30 px-3 py-2 text-gray-100"
          placeholder="Local baseline"
        />
        <input
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          className="rounded-md border border-white/10 bg-black/30 px-3 py-2 text-gray-100"
          placeholder="Notes"
        />
        <button
          type="button"
          onClick={() => void handleSnapshot()}
          className="rounded-md bg-board-accent px-4 py-2 font-semibold text-black"
        >
          Save Snapshot
        </button>
      </div>
      {status && <p className="text-sm text-emerald-300">{status}</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {runs.map((run) => (
          <div key={run.run_id} className="rounded-md border border-white/10 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold text-white">{run.label}</h3>
                <p className="text-xs text-gray-500">{new Date(run.created_at).toLocaleString()}</p>
              </div>
              <span className="badge">{run.benchmark_case_ids.length} cases</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
              <p className="text-gray-400">Precision</p>
              <p className="text-right text-gray-200">{metricLabel(run.metrics.estimated_precision)}</p>
              <p className="text-gray-400">Recall</p>
              <p className="text-right text-gray-200">{metricLabel(run.metrics.estimated_recall)}</p>
              <p className="text-gray-400">Uncertainty</p>
              <p className="text-right text-gray-200">{metricLabel(run.metrics.uncertainty_rate)}</p>
              <p className="text-gray-400">Correction</p>
              <p className="text-right text-gray-200">{metricLabel(run.metrics.correction_rate)}</p>
            </div>
            {run.notes && <p className="mt-3 text-xs text-gray-500">{run.notes}</p>}
          </div>
        ))}
        {runs.length === 0 && <p className="text-sm text-gray-500">No benchmark snapshots yet.</p>}
      </div>
    </section>
  );
}
