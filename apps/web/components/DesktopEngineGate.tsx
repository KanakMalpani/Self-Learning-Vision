"use client";

import { useEffect, useState } from "react";
import { fetchReadiness } from "@/lib/api-client";
import { getRuntimeConfig, type RuntimeConfig } from "@/lib/runtime-config";

type GateState =
  | { status: "loading"; config?: RuntimeConfig; message: string }
  | { status: "ready"; config: RuntimeConfig }
  | { status: "failed"; config?: RuntimeConfig; message: string; detail: string };

export default function DesktopEngineGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<GateState>({
    status: "loading",
    message: "Starting local engine...",
  });

  useEffect(() => {
    let active = true;

    async function check() {
      const config = await getRuntimeConfig();
      if (!config.desktopMode) {
        if (active) setState({ status: "ready", config });
        return;
      }

      const startedAt = Date.now();
      let lastError = "";
      while (active && Date.now() - startedAt < 30_000) {
        try {
          const readiness = await fetchReadiness();
          if (readiness.status === "ok") {
            setState({ status: "ready", config });
            return;
          }
          lastError = JSON.stringify(readiness, null, 2);
        } catch (error) {
          lastError = error instanceof Error ? error.message : "Local engine did not respond.";
        }
        await new Promise((resolve) => setTimeout(resolve, 750));
      }

      if (active) {
        setState({
          status: "failed",
          config,
          message: "Local engine failed to start.",
          detail: lastError || "No diagnostics were returned.",
        });
      }
    }

    void check();
    return () => {
      active = false;
    };
  }, []);

  if (state.status === "ready") {
    return <>{children}</>;
  }

  return (
    <main className="min-h-screen px-4 py-12">
      <section className="mx-auto max-w-2xl rounded-lg border border-white/10 bg-black/30 p-6 shadow-xl">
        <p className="text-sm uppercase tracking-wide text-gray-400">Self-Learning Vision</p>
        <h1 className="mt-2 text-2xl font-bold text-white">
          {state.status === "loading" ? state.message : state.message}
        </h1>
        <p className="mt-3 text-sm text-gray-400">
          {state.status === "loading"
            ? "Preparing the private local API, SQLite database, and app-data folders."
            : "The desktop shell could not reach the bundled local API sidecar."}
        </p>
        {state.config && (
          <div className="mt-4 rounded-md border border-white/10 bg-black/30 p-3 text-xs text-gray-300">
            <p>API: {state.config.apiBaseUrl}</p>
            {state.config.appDataDir && <p>Data: {state.config.appDataDir}</p>}
          </div>
        )}
        {state.status === "failed" && (
          <textarea
            readOnly
            value={state.detail}
            className="mt-4 h-40 w-full rounded-md border border-red-400/30 bg-black/40 p-3 font-mono text-xs text-red-100"
          />
        )}
      </section>
    </main>
  );
}
