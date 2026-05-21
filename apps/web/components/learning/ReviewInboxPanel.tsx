"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type {
  ActiveLearningQuestionItem,
  LearningPolicyItem,
  LearningPolicySimulationResponse,
  LearningReviewInboxResponse,
  LearningSignalItem,
} from "@/types/memory";
import {
  dismissLearningSignal,
  fetchLearningPolicy,
  fetchLearningReviewInbox,
  replayMemoryLearning,
  respondToActiveLearningQuestion,
  simulateLearningPolicy,
  updateLearningPolicy,
} from "@/lib/api-client";

type LoadState = "loading" | "ready" | "error";

function percent(value: number | undefined | null): string {
  if (value === undefined || value === null) return "0%";
  return `${Math.round(value * 100)}%`;
}

function entityIdFromSuggestion(suggestionId: string): string | null {
  const parts = suggestionId.split(":");
  return parts.length > 1 ? parts[parts.length - 1] || null : null;
}

export default function ReviewInboxPanel() {
  const [inbox, setInbox] = useState<LearningReviewInboxResponse | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [riskFilter, setRiskFilter] = useState("all");
  const [domainFilter, setDomainFilter] = useState("all");
  const [policy, setPolicy] = useState<LearningPolicyItem | null>(null);
  const [simulation, setSimulation] = useState<LearningPolicySimulationResponse | null>(null);

  async function load() {
    setState("loading");
    setError("");
    try {
      const [nextInbox, nextPolicy, nextSimulation] = await Promise.all([
        fetchLearningReviewInbox(),
        fetchLearningPolicy(),
        simulateLearningPolicy(),
      ]);
      setInbox(nextInbox);
      setPolicy(nextPolicy);
      setSimulation(nextSimulation);
      setState("ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load review inbox");
      setState("error");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const summary = inbox?.summary || {};
  const domains = useMemo(() => {
    const all = [
      ...(inbox?.questions || []).map((item) => item.domain_type),
      ...(inbox?.signals || []).map((item) => item.domain_type),
      ...(inbox?.candidate_memories || []).map((item) => item.entity.domain_type),
      ...(inbox?.low_health_memories || []).map((item) => item.entity.domain_type),
    ].filter(Boolean);
    return Array.from(new Set(all)).sort();
  }, [inbox]);
  const visibleQuestions = useMemo(
    () =>
      (inbox?.questions || []).filter(
        (item) =>
          (riskFilter === "all" || item.risk_level === riskFilter) &&
          (domainFilter === "all" || item.domain_type === domainFilter)
      ),
    [domainFilter, inbox, riskFilter]
  );
  const visibleContradictions = useMemo(
    () =>
      (inbox?.contradictions || []).filter(
        (item) =>
          (riskFilter === "all" || item.risk_level === riskFilter) &&
          (domainFilter === "all" || item.domain_type === domainFilter)
      ),
    [domainFilter, inbox, riskFilter]
  );
  const visibleCandidateMemories = useMemo(
    () =>
      (inbox?.candidate_memories || []).filter(
        (row) => domainFilter === "all" || row.entity.domain_type === domainFilter
      ),
    [domainFilter, inbox]
  );
  const visibleLowHealthMemories = useMemo(
    () =>
      (inbox?.low_health_memories || []).filter(
        (row) => domainFilter === "all" || row.entity.domain_type === domainFilter
      ),
    [domainFilter, inbox]
  );
  const topSignals = useMemo(
    () =>
      (inbox?.signals || [])
        .filter(
          (item) =>
            (riskFilter === "all" || item.risk_level === riskFilter) &&
            (domainFilter === "all" || item.domain_type === domainFilter)
        )
        .slice(0, 6),
    [domainFilter, inbox, riskFilter]
  );

  async function answer(question: ActiveLearningQuestionItem, action: "confirm" | "reject" | "dismiss" | "skip" | "label") {
    const label = labels[question.question_id]?.trim();
    if (action === "label" && !label) {
      setStatus("Add a label before applying this question.");
      return;
    }
    await respondToActiveLearningQuestion(question.question_id, {
      action,
      label: action === "label" ? label : undefined,
    });
    setStatus(`Question ${action} recorded.`);
    await load();
  }

  async function dismiss(signal: LearningSignalItem) {
    await dismissLearningSignal(signal.signal_id, { reason: "Dismissed from review inbox" });
    setStatus("Signal dismissed.");
    await load();
  }

  async function replay(entityId: string) {
    const result = await replayMemoryLearning(entityId);
    setStatus(result.applied ? "Learning replay applied." : "No replay changes were needed.");
    await load();
  }

  async function changePolicy(preset: "conservative" | "balanced" | "experimental") {
    await updateLearningPolicy({ preset });
    setStatus(`Learning policy set to ${preset}.`);
    await load();
  }

  async function confirmSafeQuestions() {
    const safe = visibleQuestions.filter(
      (question) =>
        question.question_type === "confirm_match" &&
        question.risk_level !== "high" &&
        question.confidence >= 0.85
    );
    for (const question of safe) {
      await respondToActiveLearningQuestion(question.question_id, { action: "confirm" });
    }
    setStatus(`Confirmed ${safe.length} safe high-confidence question(s).`);
    await load();
  }

  return (
    <section className="space-y-5">
      {state === "loading" && <div className="card p-4 text-gray-300">Loading learning review...</div>}
      {state === "error" && (
        <div className="card p-4 text-red-300" role="alert">
          {error}
        </div>
      )}
      {status && <div className="card p-3 text-sm text-emerald-300">{status}</div>}

      {inbox && (
        <>
          <section className="card p-5 space-y-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-400">Learning Policy</p>
                <h2 className="text-xl font-semibold">{policy?.preset || "balanced"}</h2>
                <p className="mt-1 text-sm text-gray-500">
                  Simulator: {simulation?.auto_reinforce_count || 0} auto, {simulation?.needs_review_count || 0} review, {simulation?.blocked_count || 0} blocked.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {(["conservative", "balanced", "experimental"] as const).map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => void changePolicy(preset)}
                    className={`rounded-md border px-3 py-2 text-sm font-semibold ${
                      policy?.preset === preset
                        ? "border-board-accent bg-board-accent text-black"
                        : "border-white/10 text-gray-100"
                    }`}
                  >
                    {preset}
                  </button>
                ))}
              </div>
            </div>
          </section>

          <section className="card p-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="flex flex-wrap gap-2">
                <select
                  value={riskFilter}
                  onChange={(event) => setRiskFilter(event.target.value)}
                  className="rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white"
                >
                  <option value="all">All risks</option>
                  <option value="high">High risk</option>
                  <option value="medium">Medium risk</option>
                  <option value="low">Low risk</option>
                </select>
                <select
                  value={domainFilter}
                  onChange={(event) => setDomainFilter(event.target.value)}
                  className="rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white"
                >
                  <option value="all">All domains</option>
                  {domains.map((domain) => (
                    <option key={domain} value={domain}>
                      {domain}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                onClick={() => void confirmSafeQuestions()}
                className="rounded-md border border-white/10 px-3 py-2 text-sm font-semibold text-gray-100"
              >
                Confirm Safe
              </button>
            </div>
          </section>

          <section className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {[
              ["Questions", summary.pending_question_count],
              ["Signals", summary.pending_signal_count],
              ["Conflicts", summary.contradiction_count],
              ["Candidates", summary.candidate_memory_count],
              ["Low Health", summary.low_health_memory_count],
              ["Replay", summary.replay_suggestion_count],
            ].map(([label, value]) => (
              <div key={label} className="card p-3 min-h-[5.75rem]">
                <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
                <p className="mt-2 text-2xl font-semibold">{Number(value || 0)}</p>
              </div>
            ))}
          </section>

          <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="card p-5 space-y-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-400">Highest Value</p>
                <h2 className="text-xl font-semibold">Questions</h2>
              </div>
              {visibleQuestions.map((question) => (
                <div key={question.question_id} className="rounded-md border border-white/10 p-3 space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm text-gray-100">{question.prompt}</p>
                      <p className="mt-1 text-xs text-gray-500">{question.priority_reason || question.suggested_action}</p>
                    </div>
                    <span className="badge">{question.priority}</span>
                  </div>
                  {question.question_type === "label_unknown_cluster" && (
                    <input
                      value={labels[question.question_id] || ""}
                      onChange={(event) =>
                        setLabels((current) => ({ ...current, [question.question_id]: event.target.value }))
                      }
                      placeholder="Name this memory"
                      className="w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white"
                    />
                  )}
                  <div className="flex flex-wrap gap-2">
                    {question.question_type === "label_unknown_cluster" ? (
                      <button className="rounded-md bg-board-accent px-3 py-1.5 text-sm font-semibold text-black" onClick={() => void answer(question, "label")}>
                        Label
                      </button>
                    ) : (
                      <button className="rounded-md bg-board-accent px-3 py-1.5 text-sm font-semibold text-black" onClick={() => void answer(question, "confirm")}>
                        Confirm
                      </button>
                    )}
                    <button className="rounded-md border border-white/10 px-3 py-1.5 text-sm text-gray-100" onClick={() => void answer(question, "reject")}>
                      Reject
                    </button>
                    <button className="rounded-md border border-white/10 px-3 py-1.5 text-sm text-gray-100" onClick={() => void answer(question, "dismiss")}>
                      Dismiss
                    </button>
                    <button className="rounded-md border border-white/10 px-3 py-1.5 text-sm text-gray-100" onClick={() => void answer(question, "skip")}>
                      Skip
                    </button>
                  </div>
                </div>
              ))}
              {visibleQuestions.length === 0 && <p className="text-sm text-gray-500">No active questions need review.</p>}
            </div>

            <div className="card p-5 space-y-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-400">Conflicts</p>
                <h2 className="text-xl font-semibold">Contradictions</h2>
              </div>
              {visibleContradictions.map((signal) => (
                <div key={signal.signal_id} className="rounded-md border border-white/10 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm text-gray-100">{signal.summary}</p>
                      <p className="mt-1 text-xs text-gray-500">{signal.signal_type} - {signal.risk_level}</p>
                    </div>
                    {signal.entity_id && (
                      <Link href={`/memories/detail?id=${encodeURIComponent(signal.entity_id)}`} className="rounded-md border border-white/10 px-3 py-1.5 text-sm text-gray-100">
                        Open
                      </Link>
                    )}
                  </div>
                  <button className="mt-3 rounded-md border border-white/10 px-3 py-1.5 text-sm text-gray-100" onClick={() => void dismiss(signal)}>
                    Dismiss
                  </button>
                </div>
              ))}
              {visibleContradictions.length === 0 && <p className="text-sm text-gray-500">No contradictions are pending.</p>}
            </div>
          </section>

          <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {[
              ["Candidate Memories", visibleCandidateMemories],
              ["Low Health Memories", visibleLowHealthMemories],
            ].map(([title, rows]) => (
              <div key={String(title)} className="card p-5 space-y-4">
                <h2 className="text-xl font-semibold">{String(title)}</h2>
                {(rows as LearningReviewInboxResponse["candidate_memories"]).map((row) => (
                  <div key={`${title}-${row.entity.entity_id}`} className="rounded-md border border-white/10 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-white">{row.entity.label}</p>
                        <p className="text-xs text-gray-500">{row.entity.domain_type} - {row.health.state}</p>
                      </div>
                      <span className="badge">{percent(row.health.score)}</span>
                    </div>
                    <p className="mt-2 text-sm text-gray-400">{row.health.reasons.join(", ")}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Link href={`/memories/detail?id=${encodeURIComponent(row.entity.entity_id)}`} className="rounded-md border border-white/10 px-3 py-1.5 text-sm text-gray-100">
                        Open
                      </Link>
                      <button className="rounded-md bg-board-accent px-3 py-1.5 text-sm font-semibold text-black" onClick={() => void replay(row.entity.entity_id)}>
                        Apply Replay
                      </button>
                    </div>
                  </div>
                ))}
                {(rows as LearningReviewInboxResponse["candidate_memories"]).length === 0 && <p className="text-sm text-gray-500">Nothing in this queue.</p>}
              </div>
            ))}
          </section>

          <section className="card p-5 space-y-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-400">Passive Learning</p>
              <h2 className="text-xl font-semibold">Recent Signals</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {topSignals.map((signal) => (
                <div key={signal.signal_id} className="rounded-md border border-white/10 p-3">
                  <p className="text-sm text-gray-100">{signal.summary}</p>
                  <p className="mt-1 text-xs text-gray-500">{signal.signal_type} - {percent(signal.learning_value)}</p>
                </div>
              ))}
              {topSignals.length === 0 && <p className="text-sm text-gray-500">No passive signals are pending.</p>}
            </div>
          </section>

          <section className="card p-5 space-y-4">
            <h2 className="text-xl font-semibold">Replay Suggestions</h2>
            {inbox.replay_suggestions.map((suggestion) => {
              const entityId = entityIdFromSuggestion(suggestion.suggestion_id);
              return (
                <div key={suggestion.suggestion_id} className="rounded-md border border-white/10 p-3">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="font-semibold text-white">{suggestion.title}</p>
                      <p className="mt-1 text-sm text-gray-400">{suggestion.summary}</p>
                    </div>
                    {entityId && (
                      <button className="rounded-md bg-board-accent px-3 py-1.5 text-sm font-semibold text-black" onClick={() => void replay(entityId)}>
                        Apply
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
            {inbox.replay_suggestions.length === 0 && <p className="text-sm text-gray-500">No replay suggestions yet.</p>}
          </section>
        </>
      )}
    </section>
  );
}
