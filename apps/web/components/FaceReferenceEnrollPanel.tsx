"use client";

import React, { useMemo, useState } from "react";
import { enrollMemoryRunFaceReference } from "@/lib/api-client";

interface Props {
  memory_runId: string;
  selectedFaceIndex: number;
  suggestedName?: string;
  disabled?: boolean;
  onEnrolled?: (payload: { totalReferences: number; name: string }) => void;
}

export default function FaceReferenceEnrollPanel({
  memory_runId,
  selectedFaceIndex,
  suggestedName = "",
  disabled = false,
  onEnrolled,
}: Props) {
  const [name, setName] = useState(suggestedName);
  const [notes, setNotes] = useState("");
  const [tags, setTags] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const canSave = useMemo(() => name.trim().length > 0 && !saving && !disabled, [name, saving, disabled]);

  const handleSave = async () => {
    if (!canSave) {
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await enrollMemoryRunFaceReference(memory_runId, {
        name_or_alias: name.trim(),
        notes: notes.trim() || null,
        tags: tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
        selected_face_index: selectedFaceIndex,
      });
      setSuccess(`Saved ${result.reference.name_or_alias} as a known face reference.`);
      onEnrolled?.({
        totalReferences: result.total_references,
        name: result.reference.name_or_alias,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to enroll face reference");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="card p-4 space-y-4" aria-label="Face reference enrollment">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-400">Local memory</p>
          <h2 className="text-lg font-semibold">Save as known face</h2>
        </div>
        <span className="badge bg-white/10 text-gray-100">Selected face #{selectedFaceIndex}</span>
      </div>

      <p className="text-sm text-gray-300">
        After you verify who this is, save the face to your local memory so future uploads can recognize them without external lookup.
      </p>

      <label className="block text-sm text-gray-300" htmlFor="reference-name">
        Person name or alias
        <input
          id="reference-name"
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="mt-1 w-full rounded-md bg-black/30 border border-white/15 px-3 py-2 text-sm"
          placeholder="Enter the name or alias to remember"
          autoComplete="off"
        />
      </label>

      <label className="block text-sm text-gray-300" htmlFor="reference-tags">
        Tags
        <input
          id="reference-tags"
          type="text"
          value={tags}
          onChange={(event) => setTags(event.target.value)}
          className="mt-1 w-full rounded-md bg-black/30 border border-white/15 px-3 py-2 text-sm"
          placeholder="Optional tags, separated by commas"
          autoComplete="off"
        />
      </label>

      <label className="block text-sm text-gray-300" htmlFor="reference-notes">
        Notes
        <textarea
          id="reference-notes"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          rows={3}
          className="mt-1 w-full rounded-md bg-black/30 border border-white/15 px-3 py-2 text-sm"
          placeholder="Optional context, like where you met or why they matter"
        />
      </label>

      <button
        type="button"
        disabled={!canSave}
        onClick={() => void handleSave()}
        className="px-4 py-2 rounded-md bg-board-accent text-white font-semibold disabled:opacity-50 disabled:cursor-not-allowed hover:brightness-110 transition-colors"
      >
        {saving ? "Saving..." : "Save reference"}
      </button>

      {error && <p className="text-sm text-red-300" role="alert">{error}</p>}
      {success && <p className="text-sm text-emerald-300" role="status">{success}</p>}
    </section>
  );
}

