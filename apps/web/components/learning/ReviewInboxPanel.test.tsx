import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ReviewInboxPanel from "@/components/learning/ReviewInboxPanel";
import type { LearningReviewInboxResponse } from "@/types/memory";

const apiMocks = vi.hoisted(() => ({
  fetchLearningReviewInbox: vi.fn(),
  fetchLearningPolicy: vi.fn(),
  updateLearningPolicy: vi.fn(),
  simulateLearningPolicy: vi.fn(),
  respondToActiveLearningQuestion: vi.fn(),
  dismissLearningSignal: vi.fn(),
  replayMemoryLearning: vi.fn(),
}));

vi.mock("@/lib/api-client", () => ({
  fetchLearningReviewInbox: () => apiMocks.fetchLearningReviewInbox(),
  fetchLearningPolicy: () => apiMocks.fetchLearningPolicy(),
  updateLearningPolicy: (payload: unknown) => apiMocks.updateLearningPolicy(payload),
  simulateLearningPolicy: () => apiMocks.simulateLearningPolicy(),
  respondToActiveLearningQuestion: (questionId: string, payload: unknown) =>
    apiMocks.respondToActiveLearningQuestion(questionId, payload),
  dismissLearningSignal: (signalId: string, payload: unknown) =>
    apiMocks.dismissLearningSignal(signalId, payload),
  replayMemoryLearning: (entityId: string) => apiMocks.replayMemoryLearning(entityId),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const entity = {
  entity_id: "entity-a",
  domain_type: "person",
  label: "Ada",
  attributes: {},
  schema_version: "1.0",
  user_schema: {},
  aliases: [],
  tags: [],
  notes: null,
  confidence: 0.8,
  lifecycle_state: "confirmed",
  observations: [],
  lifecycle_events: [],
  source_reference_ids: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const inbox: LearningReviewInboxResponse = {
  questions: [
    {
      question_id: "question-a",
      question_type: "confirm_match",
      prompt: "Is this Ada?",
      domain_type: "person",
      status: "pending",
      priority: 95,
      priority_reason: "tentative match can prevent a false memory",
      confidence: 0.62,
      source_signal_ids: ["signal-a"],
      learning_value: 0.95,
      risk_level: "medium",
      cooldown_until: null,
      suggested_action: "confirm_or_reject_match",
      candidate_label: "Ada",
      context: {},
      response: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
  ],
  contradictions: [],
  candidate_memories: [],
  low_health_memories: [
    {
      entity,
      health: {
        entity_id: "entity-a",
        score: 0.42,
        state: "needs_review",
        reasons: ["conflicting evidence exists"],
        confidence: 0.8,
        observation_count: 1,
        evidence_count: 2,
        contradiction_count: 1,
        correction_count: 0,
        pending_question_count: 1,
        last_updated_at: "2026-01-01T00:00:00Z",
      },
    },
  ],
  replay_suggestions: [],
  signals: [],
  summary: {
    pending_question_count: 1,
    pending_signal_count: 0,
    contradiction_count: 0,
    candidate_memory_count: 0,
    low_health_memory_count: 1,
    replay_suggestion_count: 0,
  },
};

describe("ReviewInboxPanel", () => {
  it("renders prioritized questions and applies compact actions", async () => {
    apiMocks.fetchLearningReviewInbox.mockResolvedValue(inbox);
    apiMocks.fetchLearningPolicy.mockResolvedValue({
      preset: "balanced",
      auto_reinforcement_enabled: true,
      high_confidence_threshold: 0.85,
      min_reinforcement_signals: 2,
      max_reinforcement_amount: 0.1,
      review_budget_per_session: 6,
      updated_at: "2026-01-01T00:00:00Z",
    });
    apiMocks.simulateLearningPolicy.mockResolvedValue({
      preset: "balanced",
      auto_reinforcement_enabled: true,
      auto_reinforce_count: 1,
      needs_review_count: 2,
      blocked_count: 0,
      review_budget_per_session: 6,
      auto_reinforce: [],
      needs_review: [],
      blocked: [],
    });
    apiMocks.respondToActiveLearningQuestion.mockResolvedValue({ applied: true, result: {}, question: inbox.questions[0] });
    apiMocks.replayMemoryLearning.mockResolvedValue({
      applied: true,
      affected_signal_ids: [],
      queued_question_ids: [],
      suggestions: [],
      summary: {},
    });

    render(<ReviewInboxPanel />);

    expect(await screen.findByText("Is this Ada?")).toBeInTheDocument();
    expect(screen.getByText(/tentative match can prevent/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText("Confirm"));

    await waitFor(() => {
      expect(apiMocks.respondToActiveLearningQuestion).toHaveBeenCalledWith("question-a", {
        action: "confirm",
        label: undefined,
      });
    });
  });
});
