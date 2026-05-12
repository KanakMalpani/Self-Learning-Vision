import type { ConfidenceLedgerResponse } from "@/types/memory";

export default function ConfidenceLedgerPanel({ ledger }: { ledger: ConfidenceLedgerResponse | null }) {
  if (!ledger) return null;
  return (
    <section className="card p-5 space-y-4">
      <div>
        <p className="text-xs uppercase tracking-wide text-gray-400">Confidence Ledger</p>
        <h2 className="text-xl font-semibold">{ledger.label}</h2>
      </div>
      <div className="space-y-3">
        {ledger.entries.map((entry) => (
          <div key={entry.entry_id} className="rounded-md border border-white/10 p-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-white">{entry.event_type}</p>
              <span className={entry.delta < 0 ? "text-red-300" : "text-emerald-300"}>
                {entry.delta > 0 ? "+" : ""}
                {Math.round(entry.delta * 100)}%
              </span>
            </div>
            <p className="mt-1 text-xs text-gray-500">{entry.reason}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
