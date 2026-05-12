"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { FaceBox, UploadRecognitionResult, UploadResponse } from "@/types/memory";
import { enrollMemoryRunFaceReference, startMemoryRun, uploadImage } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { AUTH_ENABLED } from "@/lib/auth-mode";

interface Props {
  onMemoryRunStart: (id: string) => void;
  onUploadComplete: (payload: UploadResponse) => void;
}

export default function UploadForm({ onMemoryRunStart, onUploadComplete }: Props) {
  const router = useRouter();
  const { logout } = useAuth();
  
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [faces, setFaces] = useState<FaceBox[]>([]);
  const [selectedFace, setSelectedFace] = useState<number>(0);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [memory_runId, setMemoryRunId] = useState<string | null>(null);
  const [recognitionResult, setRecognitionResult] = useState<UploadRecognitionResult | null>(null);
  const [enrollName, setEnrollName] = useState("");
  const [enrollNotes, setEnrollNotes] = useState("");
  const [enrollTags, setEnrollTags] = useState("");
  const [enrolling, setEnrolling] = useState(false);
  const [enrollSuccess, setEnrollSuccess] = useState<string | null>(null);
  const lastSeenLabel = recognitionResult?.last_seen_at
    ? new Date(recognitionResult.last_seen_at).toLocaleString()
    : null;
  const recognitionTags = recognitionResult?.tags ?? [];
  const hasSeenCount = typeof recognitionResult?.seen_count === "number";
  const isFamiliarUnknown = Boolean(
    recognitionResult?.status === "unknown"
      && recognitionResult.unknown_cluster_suggested_for_enrollment
      && recognitionResult.unknown_cluster_sighting_count > 1
  );
  const canEnroll = Boolean(
    memory_runId
      && uploadId
      && faces.length > 0
      && enrollName.trim()
      && !uploading
      && !enrolling
  );

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const result = await uploadImage(file);
      setFaces(result.face_boxes);
      setUploadId(result.upload_id);
      setSelectedFace(0);
      setMemoryRunId(null);
      setRecognitionResult(null);
      setEnrollSuccess(null);
      onUploadComplete(result);
    } catch (err: any) {
      // Handle 401 by logging out and redirecting
      if (err.status === 401) {
        if (AUTH_ENABLED) {
          logout();
          router.push("/login?message=Session+expired");
        } else {
          setError("Unauthorized request");
        }
      } else {
        setError(err.message || "Upload failed");
      }
    } finally {
      setUploading(false);
    }
  };

  const handleInvestigate = async () => {
    if (!uploadId) return;
    setUploading(true);
    setError(null);
    try {
      const res = await startMemoryRun(uploadId, selectedFace, notes);
      setMemoryRunId(res.memory_run_id);
      setRecognitionResult(res.recognition_result || null);
      setEnrollSuccess(null);
      onMemoryRunStart(res.memory_run_id);
    } catch (err: any) {
      // Handle 401 by logging out and redirecting
      if (err.status === 401) {
        if (AUTH_ENABLED) {
          logout();
          router.push("/login?message=Session+expired");
        } else {
          setError("Unauthorized request");
        }
      } else {
        setError(err.message || "Memory run failed");
      }
    } finally {
      setUploading(false);
    }
  };

  const handleEnroll = async () => {
    if (!canEnroll || !memory_runId || !uploadId) return;

    setEnrolling(true);
    setError(null);
    setEnrollSuccess(null);
    try {
      const tags = enrollTags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean);
      const enrolled = await enrollMemoryRunFaceReference(memory_runId, {
        name_or_alias: enrollName.trim(),
        notes: enrollNotes.trim() || notes.trim() || null,
        tags,
        selected_face_index: selectedFace,
        unknown_cluster_id: isFamiliarUnknown ? recognitionResult?.unknown_cluster_id ?? null : null,
      });

      const refreshed = await startMemoryRun(uploadId, selectedFace, notes);
      setMemoryRunId(refreshed.memory_run_id);
      setRecognitionResult(refreshed.recognition_result || null);
      setEnrollSuccess(`Saved ${enrolled.reference.name_or_alias} and refreshed recognition.`);
      onMemoryRunStart(refreshed.memory_run_id);
    } catch (err: any) {
      if (err.status === 401) {
        if (AUTH_ENABLED) {
          logout();
          router.push("/login?message=Session+expired");
        } else {
          setError("Unauthorized request");
        }
      } else {
        setError(err.message || "Enrollment failed");
      }
    } finally {
      setEnrolling(false);
    }
  };

  return (
    <div className="card p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-400">Upload a face photo to remember someone</p>
          <p className="text-lg font-semibold">Local Memory Intake</p>
        </div>
        <span className="badge">Stored locally</span>
      </div>
      <p className="rounded-md border border-emerald-400/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100">
        Face references and memory notes are for your local library. The default release path does not identify people from public web data.
      </p>

      <label className="flex flex-col items-center justify-center w-full h-32 rounded-lg border border-dashed border-white/10 hover:border-board-accent/70 cursor-pointer bg-white/5">
        <div className="text-center">
          <p className="text-sm text-gray-300">Drag & drop or pick an image</p>
          <p className="text-xs text-gray-500">JPG, PNG</p>
        </div>
        <input
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
      </label>

      {file && (
        <div className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-2 text-sm text-gray-200">
          <span className="truncate">{file.name}</span>
          <button
            className="text-board-accent hover:text-yellow-200 text-xs"
            onClick={() => {
              setFile(null);
              setFaces([]);
              setUploadId(null);
              setMemoryRunId(null);
              setRecognitionResult(null);
              setEnrollSuccess(null);
            }}
          >
            Clear
          </button>
        </div>
      )}

      <textarea
        className="w-full rounded-lg bg-black/20 border border-white/10 px-3 py-2 text-sm"
        placeholder="Optional memory note (e.g., met at hackathon, gym, college)"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
      />

      <div className="flex gap-3">
        <button
          className="px-4 py-2 rounded-lg bg-board-accent text-black font-semibold disabled:opacity-60"
          disabled={!file || uploading}
          onClick={handleUpload}
        >
          {uploading ? "Working..." : "Upload & Detect Faces"}
        </button>
        <button
          className="px-4 py-2 rounded-lg border border-white/20 text-gray-100 disabled:opacity-60"
          disabled={!uploadId || faces.length === 0 || uploading}
          onClick={handleInvestigate}
        >
          Recognize Selected Face
        </button>
      </div>

      {faces.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm text-gray-400">Detected faces</p>
          <div className="flex flex-wrap gap-2">
            {faces.map((face, idx) => (
              <button
                key={idx}
                className={`px-3 py-2 rounded-lg border text-sm ${
                  selectedFace === idx
                    ? "border-board-accent bg-board-accent/10"
                    : "border-white/10 bg-white/5"
                }`}
                onClick={() => {
                  setSelectedFace(idx);
                  setRecognitionResult(null);
                  setEnrollSuccess(null);
                  setError(null);
                }}
              >
                Face {idx + 1} ({Math.round(face.score * 100)}%)
              </button>
            ))}
          </div>
        </div>
      )}

      {recognitionResult && (
        <div className="rounded-md border border-white/10 bg-white/5 p-3" role="status" aria-live="polite">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-gray-100">
              {recognitionResult.status === "matched"
                ? `Matched ${recognitionResult.top_candidate_name || "local identity"}`
                : recognitionResult.status === "tentative"
                  ? `Possible match: ${recognitionResult.top_candidate_name || "local identity"}`
                  : "Unknown face"}
            </p>
            <span className="badge bg-white/10 text-gray-100 capitalize">{recognitionResult.status}</span>
          </div>
          <p className="mt-1 text-xs text-gray-300">
            Confidence {Math.round(recognitionResult.confidence * 100)}% · {recognitionResult.reason}
          </p>
          {recognitionResult.status === "unknown" && recognitionResult.unknown_sample_stored && (
            <p className="mt-2 text-xs text-emerald-200">
              Saved as a useful unknown sample for future familiarity learning.
            </p>
          )}
          {recognitionResult.status === "unknown" && recognitionResult.unknown_cluster_sighting_count > 1 && (
            <p className="mt-2 text-xs text-amber-200">
              Seen as an unknown {recognitionResult.unknown_cluster_sighting_count} time(s).
              {recognitionResult.unknown_cluster_suggested_for_enrollment ? " Add them when you know who they are." : ""}
            </p>
          )}
          {(recognitionResult.memory_summary || hasSeenCount || recognitionTags.length > 0) && (
            <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-gray-300 sm:grid-cols-3">
              <div className="rounded-md border border-white/10 bg-black/20 p-2 sm:col-span-3">
                <p className="uppercase tracking-wide text-gray-500">Memory</p>
                <p className="mt-1 text-sm text-gray-100">
                  {recognitionResult.memory_summary || "Saved in local memory"}
                </p>
              </div>
              <div className="rounded-md border border-white/10 bg-black/20 p-2">
                <p className="uppercase tracking-wide text-gray-500">Seen</p>
                <p className="mt-1 text-sm text-gray-100">{recognitionResult.seen_count ?? 0} time(s)</p>
              </div>
              <div className="rounded-md border border-white/10 bg-black/20 p-2">
                <p className="uppercase tracking-wide text-gray-500">Last Seen</p>
                <p className="mt-1 text-sm text-gray-100">{lastSeenLabel || "Not yet"}</p>
              </div>
              <div className="rounded-md border border-white/10 bg-black/20 p-2">
                <p className="uppercase tracking-wide text-gray-500">Tags</p>
                <p className="mt-1 text-sm text-gray-100">
                  {recognitionTags.length > 0 ? recognitionTags.join(", ") : "None"}
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {recognitionResult && recognitionResult.status !== "matched" && memory_runId && (
        <div className="rounded-md border border-board-accent/25 bg-board-accent/10 p-3 space-y-3">
          <div>
            <p className="text-sm font-semibold text-gray-100">
              {isFamiliarUnknown ? "You have seen this person multiple times. Add them?" : "Add this person to local memory"}
            </p>
            <p className="text-xs text-gray-400">
              {isFamiliarUnknown
                ? "Name this familiar unknown so future uploads can recognize them locally."
                : "Name the selected face so future uploads can recognize them locally."}
            </p>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="text-xs uppercase tracking-wide text-gray-400" htmlFor="enroll-name">
              Name or alias
              <input
                id="enroll-name"
                className="mt-1 w-full rounded-md border border-white/10 bg-black/25 px-3 py-2 text-sm normal-case tracking-normal text-gray-100"
                value={enrollName}
                onChange={(event) => setEnrollName(event.target.value)}
                placeholder="Maya"
                autoComplete="off"
              />
            </label>
            <label className="text-xs uppercase tracking-wide text-gray-400" htmlFor="enroll-tags">
              Tags
              <input
                id="enroll-tags"
                className="mt-1 w-full rounded-md border border-white/10 bg-black/25 px-3 py-2 text-sm normal-case tracking-normal text-gray-100"
                value={enrollTags}
                onChange={(event) => setEnrollTags(event.target.value)}
                placeholder="gym, hackathon"
              />
            </label>
          </div>
          <label className="text-xs uppercase tracking-wide text-gray-400" htmlFor="enroll-notes">
            Notes
            <textarea
              id="enroll-notes"
              className="mt-1 w-full rounded-md border border-white/10 bg-black/25 px-3 py-2 text-sm normal-case tracking-normal text-gray-100"
              rows={2}
              value={enrollNotes}
              onChange={(event) => setEnrollNotes(event.target.value)}
              placeholder="Optional memory context"
            />
          </label>
          <button
            type="button"
            disabled={!canEnroll}
            onClick={() => void handleEnroll()}
            className="px-4 py-2 rounded-md bg-board-accent text-black font-semibold disabled:opacity-60"
          >
            {enrolling ? "Saving..." : "Save & Refresh Recognition"}
          </button>
          {enrollSuccess && <p className="text-sm text-emerald-300" role="status">{enrollSuccess}</p>}
        </div>
      )}

      {error && <p className="text-sm text-red-400">{error}</p>}
    </div>
  );
}

