"use client";

import { useState } from "react";
import { exportUserData, purgeUserData } from "@/lib/api-client";
import { ProtectedRoute } from "@/lib/protected-route";

function SettingsContent() {
  const [exportPreview, setExportPreview] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [purging, setPurging] = useState(false);

  const handleExport = async () => {
    setStatus("");
    const payload = await exportUserData();
    setExportPreview(JSON.stringify(payload, null, 2));
    setStatus("Export loaded.");
  };

  const handlePurge = async () => {
    const confirmed = window.confirm("Delete all local memory for this user? This cannot be undone.");
    if (!confirmed) return;
    setPurging(true);
    setStatus("");
    try {
      await purgeUserData();
      setExportPreview("");
      setStatus("Local memory purged.");
    } finally {
      setPurging(false);
    }
  };

  return (
    <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <header className="space-y-2">
        <p className="text-sm text-gray-400">Local data controls</p>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-sm text-gray-500">
          Export or remove local memory for the current user. Embeddings are treated as private biometric data.
        </p>
      </header>

      <section className="card p-5 space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={() => void handleExport()}
            className="px-4 py-2 rounded-md bg-board-accent text-black font-semibold"
          >
            Export Memory
          </button>
          <button
            type="button"
            disabled={purging}
            onClick={() => void handlePurge()}
            className="px-4 py-2 rounded-md border border-red-400/40 text-red-100 bg-red-500/10 disabled:opacity-60"
          >
            {purging ? "Purging..." : "Purge Local Memory"}
          </button>
        </div>
        {status && <p className="text-sm text-emerald-300">{status}</p>}
        {exportPreview && (
          <pre className="max-h-[32rem] overflow-auto rounded-md border border-white/10 bg-black/30 p-3 text-xs text-gray-200">
            {exportPreview}
          </pre>
        )}
      </section>
    </main>
  );
}

export default function SettingsPage() {
  return (
    <ProtectedRoute>
      <SettingsContent />
    </ProtectedRoute>
  );
}
