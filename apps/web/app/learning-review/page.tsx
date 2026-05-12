"use client";

import ReviewInboxPanel from "@/components/learning/ReviewInboxPanel";
import { ProtectedRoute } from "@/lib/protected-route";

function LearningReviewContent() {
  return (
    <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      <header className="space-y-2">
        <p className="text-sm text-gray-400">Active and passive learning</p>
        <h1 className="text-3xl font-bold">Review Inbox</h1>
        <p className="text-sm text-gray-500">
          Resolve the highest-value questions, contradictions, candidate memories, and replay suggestions.
        </p>
      </header>
      <ReviewInboxPanel />
    </main>
  );
}

export default function LearningReviewPage() {
  return (
    <ProtectedRoute>
      <LearningReviewContent />
    </ProtectedRoute>
  );
}
