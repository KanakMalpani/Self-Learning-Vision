"use client";

import { useEffect, useState } from "react";
import type { ConfidenceLedgerResponse, MemoryDomainTemplateItem, MemoryEntityItem } from "@/types/memory";
import ConfidenceLedgerPanel from "@/components/memory/ConfidenceLedgerPanel";
import MemoryEntityCard from "@/components/memory/MemoryEntityCard";
import MemorySearchPanel from "@/components/memory/MemorySearchPanel";
import MemoryTemplateCreator from "@/components/memory/MemoryTemplateCreator";
import {
  fetchMemoryDomainTemplates,
  fetchMemoryEntities,
  fetchMemoryEntityConfidenceLedger,
  queueMemoryEntityDomainReviewQuestions,
} from "@/lib/api-client";
import { ProtectedRoute } from "@/lib/protected-route";

function MemoriesContent() {
  const [templates, setTemplates] = useState<MemoryDomainTemplateItem[]>([]);
  const [entities, setEntities] = useState<MemoryEntityItem[]>([]);
  const [status, setStatus] = useState("");
  const [ledger, setLedger] = useState<ConfidenceLedgerResponse | null>(null);

  useEffect(() => {
    async function loadInitial() {
      const [templatePayload, entityPayload] = await Promise.all([
        fetchMemoryDomainTemplates(),
        fetchMemoryEntities(),
      ]);
      setTemplates(templatePayload.templates);
      setEntities(entityPayload.entities);
    }
    void loadInitial();
  }, []);

  async function load() {
    const [templatePayload, entityPayload] = await Promise.all([
      fetchMemoryDomainTemplates(),
      fetchMemoryEntities(),
    ]);
    setTemplates(templatePayload.templates);
    setEntities(entityPayload.entities);
  }

  async function handleLedger(entity: MemoryEntityItem) {
    setLedger(await fetchMemoryEntityConfidenceLedger(entity.entity_id));
  }

  async function handleReview(entity: MemoryEntityItem) {
    const result = await queueMemoryEntityDomainReviewQuestions(entity.entity_id);
    setStatus(`Queued ${result.questions.length} review question(s) for ${entity.label}.`);
  }

  return (
    <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      <header className="space-y-2">
        <p className="text-sm text-gray-400">Structured memory</p>
        <h1 className="text-3xl font-bold">Memories</h1>
        <p className="text-sm text-gray-500">
          Create people, objects, places, scenes, events, documents, products, and inventory memories from templates.
        </p>
      </header>

      <MemorySearchPanel />
      {status && <p className="text-sm text-emerald-300">{status}</p>}

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <MemoryTemplateCreator templates={templates} onCreated={load} />

        <div className="space-y-4 lg:col-span-2">
          <section className="card p-5 space-y-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-400">Local Memory</p>
              <h2 className="text-xl font-semibold">Saved Entities</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {entities.map((entity) => (
                <MemoryEntityCard
                  key={entity.entity_id}
                  entity={entity}
                  onLedger={handleLedger}
                  onReview={handleReview}
                />
              ))}
              {entities.length === 0 && <p className="text-sm text-gray-500">No memories yet.</p>}
            </div>
          </section>

          <ConfidenceLedgerPanel ledger={ledger} />
        </div>
      </section>
    </main>
  );
}

export default function MemoriesPage() {
  return (
    <ProtectedRoute>
      <MemoriesContent />
    </ProtectedRoute>
  );
}
