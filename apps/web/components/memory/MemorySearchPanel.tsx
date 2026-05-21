"use client";

import Link from "next/link";
import { useState } from "react";
import type { MemorySearchResponse } from "@/types/memory";
import { searchMemoryEntities } from "@/lib/api-client";

export default function MemorySearchPanel() {
  const [query, setQuery] = useState("");
  const [domainType, setDomainType] = useState("");
  const [result, setResult] = useState<MemorySearchResponse | null>(null);

  async function handleSearch() {
    setResult(await searchMemoryEntities(query, { domainType: domainType || undefined, limit: 25 }));
  }

  return (
    <section className="card p-5 space-y-4">
      <div>
        <p className="text-xs uppercase tracking-wide text-gray-400">Search</p>
        <h2 className="text-xl font-semibold">Find Memories</h2>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-[1fr_12rem_auto] gap-3">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="rounded-md border border-white/10 bg-black/30 px-3 py-2 text-gray-100"
          placeholder="Search label, tags, notes, attributes..."
        />
        <input
          value={domainType}
          onChange={(event) => setDomainType(event.target.value)}
          className="rounded-md border border-white/10 bg-black/30 px-3 py-2 text-gray-100"
          placeholder="domain"
        />
        <button
          type="button"
          onClick={() => void handleSearch()}
          className="rounded-md bg-board-accent px-4 py-2 font-semibold text-black"
        >
          Search
        </button>
      </div>
      {result && (
        <div className="space-y-2">
          <p className="text-xs text-gray-500">{result.result_count} result(s)</p>
          {result.results.map((item) => (
            <Link
              key={item.entity_id}
              href={`/memories/detail?id=${encodeURIComponent(item.entity_id)}`}
              className="block rounded-md border border-white/10 p-3 hover:bg-white/5"
            >
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-semibold text-white">{item.label}</p>
                  <p className="text-xs text-gray-500">
                    {item.domain_type} - matched {item.matched_fields.join(", ")}
                  </p>
                </div>
                <span className="badge">{Math.round(item.confidence * 100)}%</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
