"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  EvaluationDatasetResponse,
  EvaluationMetricsResponse,
  ProviderScorecardResponse,
} from "@/types/memory";
import BenchmarkHistoryPanel from "@/components/evaluation/BenchmarkHistoryPanel";
import {
  fetchEvaluationDataset,
  fetchEvaluationMetrics,
  fetchProviderScorecard,
} from "@/lib/api-client";
import { ProtectedRoute } from "@/lib/protected-route";

type LoadState = "loading" | "ready" | "error";

function formatPercent(value?: number | null): string {
  if (value === null || value === undefined) return "Needs feedback";
  return `${Math.round(value * 1000) / 10}%`;
}

function formatNumber(value?: number | null): string {
  if (value === null || value === undefined) return "0";
  return value.toLocaleString();
}

function MetricTile({
  label,
  value,
  helper,
}: {
  label: string;
  value: string;
  helper: string;
}) {
  return (
    <div className="card p-4 min-h-[7.25rem]">
      <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
      <p className="mt-2 text-xs text-gray-500">{helper}</p>
    </div>
  );
}

function EvaluationContent() {
  const [metrics, setMetrics] = useState<EvaluationMetricsResponse | null>(null);
  const [dataset, setDataset] = useState<EvaluationDatasetResponse | null>(null);
  const [scorecard, setScorecard] = useState<ProviderScorecardResponse | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let active = true;
    async function load() {
      setState("loading");
      setError("");
      try {
        const [nextMetrics, nextDataset, nextScorecard] = await Promise.all([
          fetchEvaluationMetrics(),
          fetchEvaluationDataset(),
          fetchProviderScorecard(),
        ]);
        if (!active) return;
        setMetrics(nextMetrics);
        setDataset(nextDataset);
        setScorecard(nextScorecard);
        setState("ready");
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load evaluation data");
        setState("error");
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, []);

  const decisions = metrics?.recognition_decisions || {};
  const actions = metrics?.active_learning_actions || {};
  const providerRows = scorecard?.providers || [];
  const sampleExamples = useMemo(() => (dataset?.examples || []).slice(0, 8), [dataset]);

  return (
    <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      <header className="space-y-2">
        <p className="text-sm text-gray-400">Learning quality</p>
        <h1 className="text-3xl font-bold">Evaluation</h1>
        <p className="text-sm text-gray-500">
          Measure memory quality with local correction signals, active-learning feedback, and provider scorecards.
        </p>
      </header>

      {state === "error" && (
        <section className="card p-4 text-red-300" role="alert">
          {error}
        </section>
      )}

      {state === "loading" && (
        <section className="card p-4 text-gray-300">
          Loading evaluation data...
        </section>
      )}

      {metrics && (
        <>
          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricTile
              label="Memory Runs"
              value={formatNumber(metrics.memory_runs)}
              helper="Completed recognition attempts in this local account."
            />
            <MetricTile
              label="Uncertainty"
              value={formatPercent(metrics.uncertainty_rate)}
              helper="Tentative and unknown results that need review."
            />
            <MetricTile
              label="Precision"
              value={formatPercent(metrics.estimated_precision)}
              helper="Estimated from confirmations and false-match signals."
            />
            <MetricTile
              label="Recall"
              value={formatPercent(metrics.estimated_recall)}
              helper="Estimated from learned labels and missed-match signals."
            />
          </section>

          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricTile
              label="Passive Signals"
              value={formatNumber(metrics.passive_signal_count)}
              helper="Redacted learning evidence waiting in the passive queue."
            />
            <MetricTile
              label="Auto Reinforcement"
              value={formatNumber(metrics.auto_reinforcement_count)}
              helper="Balanced-auto updates applied to existing memories."
            />
            <MetricTile
              label="Review Inbox"
              value={formatNumber(metrics.review_inbox_pending_count)}
              helper="Questions and signals still waiting for review."
            />
            <MetricTile
              label="Contradictions"
              value={formatPercent(metrics.contradiction_rate)}
              helper="Conflict pressure across the current memory set."
            />
          </section>

          <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="card p-5 space-y-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-400">Recognition</p>
                <h2 className="text-xl font-semibold">Decision Mix</h2>
              </div>
              <div className="space-y-3">
                {["matched", "tentative", "unknown"].map((key) => (
                  <div key={key} className="flex items-center justify-between gap-4">
                    <span className="capitalize text-gray-300">{key}</span>
                    <span className="font-semibold text-white">{formatNumber(decisions[key])}</span>
                  </div>
                ))}
              </div>
              <p className="text-xs text-gray-500">
                Average confidence: {formatPercent(metrics.average_recognition_confidence)}
              </p>
            </div>

            <div className="card p-5 space-y-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-400">Learning Loop</p>
                <h2 className="text-xl font-semibold">Feedback</h2>
              </div>
              <div className="space-y-3">
                {["confirm", "reject", "label", "dismiss", "skip"].map((key) => (
                  <div key={key} className="flex items-center justify-between gap-4">
                    <span className="capitalize text-gray-300">{key}</span>
                    <span className="font-semibold text-white">{formatNumber(actions[key])}</span>
                  </div>
                ))}
              </div>
              <p className="text-xs text-gray-500">
                Completion: {formatPercent(metrics.active_learning_completion_rate)}
              </p>
            </div>

            <div className="card p-5 space-y-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-400">Corrections</p>
                <h2 className="text-xl font-semibold">Memory Pressure</h2>
              </div>
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-gray-300">Corrections</span>
                  <span className="font-semibold text-white">{formatNumber(metrics.corrections)}</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-gray-300">False-match signals</span>
                  <span className="font-semibold text-white">
                    {formatNumber(metrics.false_match_signals)}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-gray-300">Missed-match signals</span>
                  <span className="font-semibold text-white">
                    {formatNumber(metrics.missed_match_signals)}
                  </span>
                </div>
              </div>
              <p className="text-xs text-gray-500">
                Correction rate: {formatPercent(metrics.correction_rate)}
              </p>
            </div>
          </section>
        </>
      )}

      {scorecard && (
        <section className="card p-5 space-y-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-gray-400">Providers</p>
            <h2 className="text-xl font-semibold">Scorecard</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {providerRows.length === 0 && (
              <p className="text-sm text-gray-500">No provider has been selected yet.</p>
            )}
            {providerRows.map((provider) => (
              <div key={provider.provider_id} className="rounded-md border border-white/10 p-4">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <h3 className="font-semibold text-white">{provider.display_name || provider.provider_id}</h3>
                  <span className="badge">{provider.cost_model || "unknown"}</span>
                </div>
                <p className="mt-2 text-sm text-gray-400">
                  {provider.mode || "provider"} - {provider.status || "unknown"}
                </p>
                <p className="mt-2 text-xs text-gray-500">{provider.privacy_notes}</p>
                <p className="mt-3 text-xs text-gray-400">
                  Selected for: {provider.selected_for.length ? provider.selected_for.join(", ") : "default"}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {dataset && (
        <section className="card p-5 space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-400">Dataset</p>
              <h2 className="text-xl font-semibold">Redacted Evaluation Set</h2>
            </div>
            <span className="badge">{dataset.example_count} examples</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-gray-400">
                <tr>
                  <th className="py-2 pr-4 font-medium">Source</th>
                  <th className="py-2 pr-4 font-medium">Task</th>
                  <th className="py-2 pr-4 font-medium">Label</th>
                  <th className="py-2 pr-4 font-medium">State</th>
                  <th className="py-2 font-medium">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {sampleExamples.map((example) => (
                  <tr key={example.example_id} className="border-t border-white/10">
                    <td className="py-2 pr-4 text-gray-300">{example.source}</td>
                    <td className="py-2 pr-4 text-gray-300">{example.task}</td>
                    <td className="py-2 pr-4 text-gray-300">{example.label || "n/a"}</td>
                    <td className="py-2 pr-4 text-gray-300">
                      {example.lifecycle_state || example.status || example.action || "n/a"}
                    </td>
                    <td className="py-2 text-gray-300">{formatPercent(example.confidence)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-gray-500">
            Redaction policy: raw images, upload paths, biometric embeddings, and provider secrets are excluded.
          </p>
        </section>
      )}

      <BenchmarkHistoryPanel />
    </main>
  );
}

export default function EvaluationPage() {
  return (
    <ProtectedRoute>
      <EvaluationContent />
    </ProtectedRoute>
  );
}
