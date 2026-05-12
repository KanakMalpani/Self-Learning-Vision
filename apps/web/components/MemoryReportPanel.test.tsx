import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MemoryReportPanel from "@/components/MemoryReportPanel";
import type { MemoryReport } from "@/types/memory";

const memory_report: MemoryReport = {
  subject: {
    name_or_alias: "Ada Lovelace",
    possible_profiles: ["https://en.wikipedia.org/wiki/Ada_Lovelace"],
  },
  executive_summary: "Ada Lovelace was identified using a local memory match.",
  key_facts: [{ title: "Role", detail: "Mathematician", confidence: 0.94 }],
  timeline: [{ title: "Born", date: "1815-12-10", description: "London", confidence: 0.9 }],
  profile_links: ["https://en.wikipedia.org/wiki/Ada_Lovelace"],
  confidence: { overall: 0.93, photo: 0.88 },
  source_notes: ["[1] Ada Lovelace | https://en.wikipedia.org/wiki/Ada_Lovelace | score=0.92"],
  caveats: ["Use public sources only."],
  face_assessments: [],
  identity_candidates: [],
  recognition_summary: {
    recognition_decision: "accepted",
    matching_strategy: "embedding",
    identity_fusion_score: 0.86,
    corroboration_summary: {
      corroborated_domain_count: 2,
      supporting_evidence_count: 2,
    },
  },
  decision_trace: {
    strategy: "embedding",
    top_candidate_name: "Ada Lovelace",
    top_candidate_score: 0.91,
    margin: 0.12,
    fusion_score: 0.86,
    recognition_decision: "accepted",
    corroboration_summary: {
      corroborated_domain_count: 2,
      supporting_evidence_count: 2,
    },
  },
  identity_explanation: [
    "Top candidate Ada Lovelace scored 0.91 via local memory.",
    "Local memory signals scored 0.92 with corroboration 0.67.",
  ],
  memory_analytics: {
    frequency: {
      raw_reference_count: 1,
      total_references: 1,
      raw_seen_count: 1,
      total_seen_count: 1,
      average_seen_count: 1,
      top_referenced_identities: [
        {
          name_or_alias: "Ada Lovelace",
          seen_count: 1,
          tags: ["verified", "team"],
          last_seen_at: "2026-04-02T00:00:00.000Z",
          variant_count: 1,
        },
      ],
    },
    tags: {
      unique_tags: ["verified", "team"],
      tag_counts: [
        { tag: "verified", count: 1 },
        { tag: "team", count: 1 },
      ],
      top_tag_pairs: [],
    },
    temporal: {
      seen_today_count: 1,
      seen_7d_count: 1,
      seen_30d_count: 1,
      never_seen_count: 0,
      future_seen_count: 0,
      oldest_last_seen_at: "2026-04-02T00:00:00.000Z",
      newest_last_seen_at: "2026-04-02T00:00:00.000Z",
      active_identity_count: 1,
    },
  },
  generated_at: "2026-04-02T00:00:00.000Z",
};

describe("MemoryReportPanel", () => {
  it("renders the decision trace and explanation", () => {
    render(<MemoryReportPanel memory_report={memory_report} />);

    expect(screen.getByText(/Identity Decision/i)).toBeInTheDocument();
    expect(screen.getByText(/^Strategy: embedding$/i)).toBeInTheDocument();
    expect(screen.getByText(/Why This Match/i)).toBeInTheDocument();
    expect(screen.getByText(/Ada Lovelace scored 0.91/i)).toBeInTheDocument();
    expect(screen.getByText(/Supporting signals: 2/i)).toBeInTheDocument();
    expect(screen.getByText(/Memory Profile/i)).toBeInTheDocument();
    expect(screen.getByText(/References/i)).toBeInTheDocument();
    expect(screen.getByText(/verified, team/i)).toBeInTheDocument();
  });
});

