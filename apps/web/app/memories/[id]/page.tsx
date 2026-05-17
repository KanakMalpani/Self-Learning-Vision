"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import ConfidenceLedgerPanel from "@/components/memory/ConfidenceLedgerPanel";
import type { MemoryEntityDetailResponse } from "@/types/memory";
import {
  fetchMemoryEntityDetail,
  forgetMemoryEntity,
  markMemoryEntityNotThis,
  queueMemoryEntityDomainReviewQuestions,
  renameMemoryEntity,
  replayMemoryLearning,
  respondToActiveLearningQuestion,
  updateMemoryEntity,
} from "@/lib/api-client";
import { ProtectedRoute } from "@/lib/protected-route";

function MemoryDetailContent({ id }: { id: string }) {
  const [detail, setDetail] = useState<MemoryEntityDetailResponse | null>(null);
  const [status, setStatus] = useState("");
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");
  const [attributesJson, setAttributesJson] = useState("{}");

  useEffect(() => {
    async function load() {
      setDetail(await fetchMemoryEntityDetail(id));
    }
    void load();
  }, [id]);

  useEffect(() => {
    if (!detail) return;
    setLabel(detail.entity.label);
    setNotes(detail.entity.notes || "");
    setAttributesJson(JSON.stringify(detail.entity.attributes || {}, null, 2));
  }, [detail]);

  async function handleReview() {
    const result = await queueMemoryEntityDomainReviewQuestions(id);
    setStatus(`Queued ${result.questions.length} review question(s).`);
    setDetail(await fetchMemoryEntityDetail(id));
  }

  async function handleReplay() {
    const result = await replayMemoryLearning(id);
    setStatus(result.applied ? "Learning replay applied." : "No replay changes were needed.");
    setDetail(await fetchMemoryEntityDetail(id));
  }

  async function handleSaveFields() {
    try {
      const attributes = JSON.parse(attributesJson || "{}");
      await updateMemoryEntity(id, { attributes, notes });
      setStatus("Memory fields saved.");
      setDetail(await fetchMemoryEntityDetail(id));
    } catch (err) {
      setStatus(err instanceof SyntaxError ? "Attributes must be valid JSON." : "Could not save memory fields.");
    }
  }

  async function handleRename() {
    if (!label.trim()) {
      setStatus("Name is required.");
      return;
    }
    await renameMemoryEntity(id, { label, notes });
    setStatus("Memory renamed.");
    setDetail(await fetchMemoryEntityDetail(id));
  }

  async function handleNotThis() {
    await markMemoryEntityNotThis(id, { rejected_label: detail?.entity.label, notes: "Marked from memory detail page" });
    setStatus("Memory marked as not-this.");
    setDetail(await fetchMemoryEntityDetail(id));
  }

  async function handleForget() {
    await forgetMemoryEntity(id, { mode: "archived", notes: "Archived from memory detail page" });
    setStatus("Memory archived.");
    setDetail(await fetchMemoryEntityDetail(id));
  }

  async function handleQuestion(questionId: string, action: "confirm" | "reject" | "dismiss" | "skip") {
    await respondToActiveLearningQuestion(questionId, { action });
    setStatus(`Question ${action} recorded.`);
    setDetail(await fetchMemoryEntityDetail(id));
  }

  if (!detail) {
    return (
      <main className="max-w-5xl mx-auto px-4 py-8">
        <section className="card p-4 text-gray-300">Loading memory...</section>
      </main>
    );
  }

  const entity = detail.entity;
  const attributes = Object.entries(entity.attributes);

  return (
    <main className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      <header className="space-y-3">
        <Link href="/memories" className="text-sm">
          Back to memories
        </Link>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-sm text-gray-400">{entity.domain_type}</p>
            <h1 className="text-3xl font-bold">{entity.label}</h1>
            <p className="text-sm text-gray-500">{entity.lifecycle_state}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {detail.health && <span className="badge">{detail.health.state}</span>}
            <span className="badge">{Math.round(entity.confidence * 100)}% confidence</span>
          </div>
        </div>
      </header>

      <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card p-4">
          <p className="text-xs uppercase tracking-wide text-gray-400">Observations</p>
          <p className="mt-2 text-2xl font-semibold">{detail.summary.observation_count || 0}</p>
        </div>
        <div className="card p-4">
          <p className="text-xs uppercase tracking-wide text-gray-400">Events</p>
          <p className="mt-2 text-2xl font-semibold">{detail.summary.lifecycle_event_count || 0}</p>
        </div>
        <div className="card p-4">
          <p className="text-xs uppercase tracking-wide text-gray-400">Corrections</p>
          <p className="mt-2 text-2xl font-semibold">{detail.summary.correction_count || 0}</p>
        </div>
        <div className="card p-4">
          <p className="text-xs uppercase tracking-wide text-gray-400">Pending</p>
          <p className="mt-2 text-2xl font-semibold">{detail.summary.pending_question_count || 0}</p>
        </div>
      </section>

      {detail.health && (
        <section className="card p-5 space-y-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-400">Memory Health</p>
              <h2 className="text-xl font-semibold">{detail.health.state}</h2>
            </div>
            <span className="badge">{Math.round(detail.health.score * 100)}%</span>
          </div>
          <p className="text-sm text-gray-400">{detail.health.reasons.join(", ")}</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div className="rounded-md border border-white/10 p-3">
              <p className="text-xs text-gray-500">Evidence</p>
              <p className="mt-1 font-semibold">{detail.health.evidence_count}</p>
            </div>
            <div className="rounded-md border border-white/10 p-3">
              <p className="text-xs text-gray-500">Contradictions</p>
              <p className="mt-1 font-semibold">{detail.health.contradiction_count}</p>
            </div>
            <div className="rounded-md border border-white/10 p-3">
              <p className="text-xs text-gray-500">Corrections</p>
              <p className="mt-1 font-semibold">{detail.health.correction_count}</p>
            </div>
            <div className="rounded-md border border-white/10 p-3">
              <p className="text-xs text-gray-500">Questions</p>
              <p className="mt-1 font-semibold">{detail.health.pending_question_count}</p>
            </div>
          </div>
        </section>
      )}

      <section className="card p-5 space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-gray-400">Attributes</p>
            <h2 className="text-xl font-semibold">Memory Fields</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void handleReview()}
              className="rounded-md bg-board-accent px-4 py-2 font-semibold text-black"
            >
              Ask Review
            </button>
            <button
              type="button"
              onClick={() => void handleReplay()}
              className="rounded-md border border-white/10 px-4 py-2 font-semibold text-gray-100"
            >
              Apply Replay
            </button>
          </div>
        </div>
        {status && <p className="text-sm text-emerald-300">{status}</p>}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {attributes.map(([key, value]) => (
            <div key={key} className="rounded-md border border-white/10 p-3">
              <p className="text-xs text-gray-500">{key.replaceAll("_", " ")}</p>
              <p className="mt-1 text-sm text-gray-200">{String(value)}</p>
            </div>
          ))}
          {attributes.length === 0 && <p className="text-sm text-gray-500">No attributes yet.</p>}
        </div>
      </section>

      <section className="card p-5 space-y-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-400">Edit</p>
          <h2 className="text-xl font-semibold">Correct This Memory</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="space-y-1">
            <span className="text-xs text-gray-500">Name</span>
            <input
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              className="w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white"
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs text-gray-500">Notes</span>
            <input
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              className="w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white"
            />
          </label>
        </div>
        <label className="block space-y-1">
          <span className="text-xs text-gray-500">Attributes JSON</span>
          <textarea
            value={attributesJson}
            onChange={(event) => setAttributesJson(event.target.value)}
            rows={7}
            className="w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 font-mono text-sm text-white"
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => void handleSaveFields()} className="rounded-md bg-board-accent px-4 py-2 font-semibold text-black">
            Save Fields
          </button>
          <button type="button" onClick={() => void handleRename()} className="rounded-md border border-white/10 px-4 py-2 font-semibold text-gray-100">
            Rename
          </button>
          <button type="button" onClick={() => void handleNotThis()} className="rounded-md border border-white/10 px-4 py-2 font-semibold text-gray-100">
            Not This
          </button>
          <button type="button" onClick={() => void handleForget()} className="rounded-md border border-white/10 px-4 py-2 font-semibold text-gray-100">
            Archive
          </button>
        </div>
      </section>

      <ConfidenceLedgerPanel ledger={detail.confidence_ledger} />

      <section className="card p-5 space-y-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-400">Timeline</p>
          <h2 className="text-xl font-semibold">Learning Timeline</h2>
        </div>
        <div className="space-y-3">
          {detail.learning_timeline.map((item) => (
            <div key={item.timeline_id} className="rounded-md border border-white/10 p-3">
              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="font-semibold text-white">{item.title}</p>
                  <p className="mt-1 text-sm text-gray-400">{item.summary}</p>
                </div>
                <span className="badge">{item.source}</span>
              </div>
              <p className="mt-2 text-xs text-gray-500">{item.created_at}</p>
            </div>
          ))}
          {detail.learning_timeline.length === 0 && <p className="text-sm text-gray-500">No learning timeline yet.</p>}
        </div>
      </section>

      <section className="card p-5 space-y-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-400">Evidence</p>
          <h2 className="text-xl font-semibold">Why This Memory Is Trusted</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {detail.evidence_bundles.map((bundle) => (
            <div key={bundle.bundle_id} className="rounded-md border border-white/10 p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-white">{bundle.title}</p>
                  <p className="mt-1 text-sm text-gray-400">{bundle.summary}</p>
                </div>
                <span className="badge">{bundle.event_count}</span>
              </div>
              <p className="mt-2 text-xs text-gray-500">
                {bundle.source} - {bundle.risk_level}
              </p>
            </div>
          ))}
          {detail.evidence_bundles.length === 0 && <p className="text-sm text-gray-500">No evidence bundles yet.</p>}
        </div>
      </section>

      {(detail.related_conflicts.length > 0 || detail.replay_suggestions.length > 0) && (
        <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="card p-5 space-y-3">
            <h2 className="text-xl font-semibold">Related Conflicts</h2>
            {detail.related_conflicts.map((conflict, index) => (
              <div key={`${String(conflict.conflict_id || "conflict")}-${index}`} className="rounded-md border border-white/10 p-3">
                <p className="text-sm text-gray-200">{String(conflict.summary || "Conflict needs review")}</p>
                <p className="mt-1 text-xs text-gray-500">{String(conflict.conflict_type || "conflict")}</p>
              </div>
            ))}
            {detail.related_conflicts.length === 0 && <p className="text-sm text-gray-500">No conflicts found.</p>}
          </div>
          <div className="card p-5 space-y-3">
            <h2 className="text-xl font-semibold">Replay Suggestions</h2>
            {detail.replay_suggestions.map((suggestion) => (
              <div key={suggestion.suggestion_id} className="rounded-md border border-white/10 p-3">
                <p className="text-sm font-semibold text-gray-100">{suggestion.title}</p>
                <p className="mt-1 text-sm text-gray-400">{suggestion.summary}</p>
              </div>
            ))}
            {detail.replay_suggestions.length === 0 && <p className="text-sm text-gray-500">No replay suggestions.</p>}
          </div>
        </section>
      )}

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card p-5 space-y-3">
          <h2 className="text-xl font-semibold">Active Learning</h2>
          {detail.active_learning_questions.map((question) => (
            <div key={question.question_id} className="rounded-md border border-white/10 p-3 space-y-3">
              <p className="text-sm text-gray-200">{question.prompt}</p>
              <p className="mt-1 text-xs text-gray-500">{question.status}</p>
              {question.status === "pending" && (
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => void handleQuestion(question.question_id, "confirm")} className="rounded-md bg-board-accent px-3 py-1.5 text-sm font-semibold text-black">
                    Confirm
                  </button>
                  <button type="button" onClick={() => void handleQuestion(question.question_id, "reject")} className="rounded-md border border-white/10 px-3 py-1.5 text-sm text-gray-100">
                    Reject
                  </button>
                  <button type="button" onClick={() => void handleQuestion(question.question_id, "dismiss")} className="rounded-md border border-white/10 px-3 py-1.5 text-sm text-gray-100">
                    Dismiss
                  </button>
                </div>
              )}
            </div>
          ))}
          {detail.active_learning_questions.length === 0 && (
            <p className="text-sm text-gray-500">No review questions yet.</p>
          )}
        </div>
        <div className="card p-5 space-y-3">
          <h2 className="text-xl font-semibold">Corrections</h2>
          {detail.corrections.map((correction) => (
            <div key={correction.correction_id} className="rounded-md border border-white/10 p-3">
              <p className="text-sm text-gray-200">{correction.summary}</p>
              <p className="mt-1 text-xs text-gray-500">{correction.operation_type}</p>
            </div>
          ))}
          {detail.corrections.length === 0 && <p className="text-sm text-gray-500">No corrections yet.</p>}
        </div>
      </section>
    </main>
  );
}

export default function MemoryDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;

  if (!id) {
    return (
      <ProtectedRoute>
        <main className="max-w-5xl mx-auto px-4 py-8">
          <section className="card p-4 text-gray-300">Missing memory id.</section>
        </main>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <MemoryDetailContent id={id} />
    </ProtectedRoute>
  );
}
