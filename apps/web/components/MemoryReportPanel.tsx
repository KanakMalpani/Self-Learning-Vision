"use client";

import React from "react";
import type { MemoryReport } from "@/types/memory";

interface Props {
  memory_report?: MemoryReport;
}

export default function MemoryReportPanel({ memory_report }: Props) {
  if (!memory_report) {
    return (
      <div className="card p-4">
        <p className="text-sm text-gray-400">No memory result yet. Upload a photo and recognize a face.</p>
      </div>
    );
  }

  const decisionTrace = memory_report.decision_trace ?? {};
  const identityExplanation = memory_report.identity_explanation ?? [];
  const memoryAnalytics = memory_report.memory_analytics ?? {};
  const recognitionSummary = memory_report.recognition_summary ?? {};
  const decisionLabel = String(recognitionSummary.recognition_decision ?? "unknown");
  const finalVerdictName = String(
    recognitionSummary.final_verdict_name ?? decisionTrace.final_verdict_name ?? "Unknown"
  );
  const finalVerdictDecision = String(
    recognitionSummary.final_verdict_decision ?? decisionTrace.final_verdict_decision ?? decisionLabel
  );
  const verdictUnknown = finalVerdictName.trim().toLowerCase() === "unknown";
  const rawStrategyLabel = String(recognitionSummary.matching_strategy ?? "heuristic");
  const strategyLabel = rawStrategyLabel;
  const fusionScore = typeof decisionTrace.fusion_score === "number" ? decisionTrace.fusion_score : undefined;
  const corroboratedDomains = typeof (decisionTrace.corroboration_summary as Record<string, unknown> | undefined)?.corroborated_domain_count === "number"
    ? (decisionTrace.corroboration_summary as Record<string, number>).corroborated_domain_count
    : 0;
  const topMemoryIdentity = memoryAnalytics.frequency?.top_referenced_identities?.[0];
  const topIdentityTags = topMemoryIdentity?.tags ?? [];
  const topTags = memoryAnalytics.tags?.unique_tags ?? [];
  const temporal = memoryAnalytics.temporal ?? {};
  const formatCount = (value: number | undefined) => (value === undefined ? "–" : String(value));

  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase text-gray-400">Memory Result</p>
          <p className="text-xl font-bold">{finalVerdictName}</p>
          <p className="text-xs text-gray-500 capitalize">Decision: {finalVerdictDecision}</p>
          {verdictUnknown && (
            <span className="inline-flex mt-2 px-2 py-1 rounded-md text-xs bg-amber-500/20 text-amber-100 border border-amber-400/30">
              Unknown (no trusted match)
            </span>
          )}
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-400">Confidence</p>
          <div className="w-40 h-2 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-board-accent"
              style={{ width: `${Math.round((memory_report.confidence?.overall ?? 0) * 100)}%` }}
            />
          </div>
          <p className="text-xs text-gray-500">Overall {Math.round((memory_report.confidence?.overall ?? 0) * 100)}%</p>
          {memory_report.confidence?.photo !== undefined && (
            <p className="text-xs text-gray-500">Photo {Math.round(memory_report.confidence.photo * 100)}%</p>
          )}
        </div>
      </div>

      <div>
        <p className="text-sm text-gray-400 mb-1">Memory Summary</p>
        <p className="text-gray-100 leading-relaxed">{memory_report.executive_summary}</p>
        {verdictUnknown && (
          <p className="text-xs text-amber-200 mt-2">
            No local memory produced a confident person-name match for this face.
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="rounded-lg border border-white/10 bg-white/5 p-3 space-y-1">
          <p className="text-xs uppercase tracking-wide text-gray-400">Identity Decision</p>
          <p className="text-lg font-semibold capitalize">{decisionLabel}</p>
          <p className="text-xs text-gray-500">Strategy: {strategyLabel}</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/5 p-3 space-y-1">
          <p className="text-xs uppercase tracking-wide text-gray-400">Match Score</p>
          <p className="text-lg font-semibold">{fusionScore !== undefined ? Math.round(fusionScore * 100) + "%" : "–"}</p>
          <p className="text-xs text-gray-500">Combined face-memory confidence</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/5 p-3 space-y-1">
          <p className="text-xs uppercase tracking-wide text-gray-400">Candidate Gap</p>
          <p className="text-lg font-semibold">{typeof decisionTrace.margin === "number" ? `Margin ${Math.round(decisionTrace.margin * 100)}%` : "No margin"}</p>
          <p className="text-xs text-gray-500">Top candidate vs runner-up</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="bg-white/5 rounded-lg p-3 border border-white/5">
          <p className="text-sm font-semibold mb-2">Why This Match</p>
          <ul className="space-y-2 text-sm text-gray-100 list-disc list-inside">
            {identityExplanation.length === 0 && <li className="text-gray-500">No explanation available yet.</li>}
            {identityExplanation.map((line, index) => (
              <li key={`${index}-${line}`}>{line}</li>
            ))}
          </ul>
        </div>

        <div className="bg-white/5 rounded-lg p-3 border border-white/5">
          <p className="text-sm font-semibold mb-2">Recognition Summary</p>
          <ul className="space-y-2 text-sm text-gray-100 list-disc list-inside">
            <li>Top candidate: {String(decisionTrace.top_candidate_name ?? "Unknown")}</li>
            <li>Top score: {typeof decisionTrace.top_candidate_score === "number" ? Math.round(decisionTrace.top_candidate_score * 100) + "%" : "–"}</li>
            <li>Memory score: {typeof recognitionSummary.identity_fusion_score === "number" ? Math.round(Number(recognitionSummary.identity_fusion_score) * 100) + "%" : "–"}</li>
            <li>Supporting signals: {corroboratedDomains}</li>
          </ul>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="bg-white/5 rounded-lg p-3 border border-white/5 space-y-2">
          <p className="text-sm font-semibold">Memory Profile</p>
          <div className="grid grid-cols-2 gap-2 text-xs text-gray-300">
            <div className="rounded-md bg-black/20 p-2 border border-white/5">
              <p className="uppercase tracking-wide text-gray-500">References</p>
              <p className="text-base text-gray-100 font-semibold">{formatCount(memoryAnalytics.frequency?.total_references)}</p>
            </div>
            <div className="rounded-md bg-black/20 p-2 border border-white/5">
              <p className="uppercase tracking-wide text-gray-500">Seen Count</p>
              <p className="text-base text-gray-100 font-semibold">{formatCount(memoryAnalytics.frequency?.total_seen_count)}</p>
            </div>
            <div className="rounded-md bg-black/20 p-2 border border-white/5">
              <p className="uppercase tracking-wide text-gray-500">Active</p>
              <p className="text-base text-gray-100 font-semibold">{formatCount(temporal.active_identity_count)}</p>
            </div>
            <div className="rounded-md bg-black/20 p-2 border border-white/5">
              <p className="uppercase tracking-wide text-gray-500">Seen 7d</p>
              <p className="text-base text-gray-100 font-semibold">{formatCount(temporal.seen_7d_count)}</p>
            </div>
          </div>
        </div>

        <div className="bg-white/5 rounded-lg p-3 border border-white/5 space-y-2">
          <p className="text-sm font-semibold">Top Memory Signal</p>
          {topMemoryIdentity ? (
            <ul className="space-y-2 text-sm text-gray-100 list-disc list-inside">
              <li>{topMemoryIdentity.name_or_alias} referenced {topMemoryIdentity.seen_count} time(s)</li>
              <li>Tags: {topIdentityTags.length > 0 ? topIdentityTags.join(", ") : "None"}</li>
              <li>Last seen: {topMemoryIdentity.last_seen_at ?? "Never"}</li>
            </ul>
          ) : (
            <p className="text-sm text-gray-500">No memory history is available yet.</p>
          )}
        </div>

        <div className="bg-white/5 rounded-lg p-3 border border-white/5 space-y-2">
          <p className="text-sm font-semibold">Common Tags</p>
          {topTags.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {topTags.map((tag) => (
                <span key={tag} className="rounded-full border border-white/10 bg-black/20 px-2 py-1 text-xs text-gray-200">
                  {tag}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500">No identity tags recorded.</p>
          )}
          <p className="text-xs text-gray-500">Today: {formatCount(temporal.seen_today_count)} | 30d: {formatCount(temporal.seen_30d_count)}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="bg-white/5 rounded-lg p-3 border border-white/5">
          <p className="text-sm font-semibold mb-2">Memory Facts</p>
          <ul className="space-y-2 text-sm text-gray-100 list-disc list-inside">
            {memory_report.key_facts?.map((fact, idx) => (
              <li key={idx}>
                <span className="font-semibold">{fact.title}:</span> {fact.detail}
                {fact.confidence !== undefined && (
                  <span className="ml-2 text-gray-400">({Math.round((fact.confidence || 0) * 100)}%)</span>
                )}
              </li>
            ))}
          </ul>
        </div>

        <div className="bg-white/5 rounded-lg p-3 border border-white/5">
          <p className="text-sm font-semibold mb-2">Timeline</p>
          <div className="space-y-2 text-sm">
              {(memory_report.timeline?.length || 0) === 0 && <p className="text-gray-400">No timeline entries.</p>}
              {memory_report.timeline?.map((item, idx) => (
              <div key={idx} className="flex items-start gap-2">
                <div className="mt-1 w-2 h-2 rounded-full bg-board-accent" />
                <div>
                  <p className="font-semibold text-gray-100">{item.title}</p>
                  <p className="text-xs text-gray-400">{item.date}</p>
                  <p className="text-gray-200">{item.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <p className="text-sm font-semibold mb-1">Reference Links</p>
          <ul className="text-sm text-board-accent space-y-1">
            {(memory_report.profile_links?.length || 0) === 0 && <li className="text-gray-500">No links yet.</li>}
            {memory_report.profile_links?.map((link, idx) => (
              <li key={idx}>
                <a href={link} target="_blank" rel="noreferrer">
                  {link}
                </a>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-sm font-semibold mb-1">Caveats & Notes</p>
          <ul className="text-sm text-gray-300 space-y-1 list-disc list-inside">
            {[...(memory_report.caveats || []), ...(memory_report.source_notes || [])].map((note, idx) => (
              <li key={idx}>{note}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}


