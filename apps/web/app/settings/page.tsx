"use client";

import { useEffect, useState } from "react";
import { exportUserData, fetchReadiness, purgeUserData } from "@/lib/api-client";
import { ProtectedRoute } from "@/lib/protected-route";
import { getRuntimeConfig, type RuntimeConfig } from "@/lib/runtime-config";
import type { ReadinessResponse } from "@/types/memory";

function SettingsContent() {
  const [exportPreview, setExportPreview] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [purging, setPurging] = useState(false);
  const [runtime, setRuntime] = useState<RuntimeConfig | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);

  useEffect(() => {
    let active = true;
    async function loadRuntime() {
      const config = await getRuntimeConfig();
      if (!active) return;
      setRuntime(config);
      try {
        setReadiness(await fetchReadiness());
      } catch {
        setReadiness(null);
      }
    }
    void loadRuntime();
    return () => {
      active = false;
    };
  }, []);

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
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-400">Runtime</p>
          <h2 className="text-xl font-semibold">Local Engine</h2>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="rounded-md border border-white/10 p-3 text-sm">
            <p className="text-xs text-gray-500">API URL</p>
            <p className="mt-1 break-all text-gray-100">{runtime?.apiBaseUrl || "Loading..."}</p>
          </div>
          <div className="rounded-md border border-white/10 p-3 text-sm">
            <p className="text-xs text-gray-500">{runtime?.desktopMode ? "Desktop App Data Directory" : "Data Directory"}</p>
            <p className="mt-1 break-all text-gray-100">{runtime?.appDataDir || String(readiness?.diagnostics.storage_dir || "Configured backend")}</p>
          </div>
          <div className="rounded-md border border-white/10 p-3 text-sm">
            <p className="text-xs text-gray-500">Database</p>
            <p className="mt-1 text-gray-100">{runtime?.databaseMode || String(readiness?.diagnostics.database_url || "configured")}</p>
          </div>
          <div className="rounded-md border border-white/10 p-3 text-sm">
            <p className="text-xs text-gray-500">Provider</p>
            <p className="mt-1 text-gray-100">{runtime?.providerMode || String(readiness?.optional_features.embedding_provider || "auto")}</p>
          </div>
          <div className="rounded-md border border-white/10 p-3 text-sm">
            <p className="text-xs text-gray-500">Privacy Mode</p>
            <p className="mt-1 text-gray-100">
              {readiness?.dependencies.privacy_local_only ? "Local only" : "Configured backend policy"}
            </p>
          </div>
          <div className="rounded-md border border-white/10 p-3 text-sm">
            <p className="text-xs text-gray-500">Desktop Network Binding</p>
            <p className="mt-1 text-gray-100">{runtime?.desktopMode ? "Loopback only (127.0.0.1)" : "Configured backend"}</p>
          </div>
        </div>
      </section>

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
