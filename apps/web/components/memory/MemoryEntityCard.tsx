import Link from "next/link";
import type { MemoryEntityItem } from "@/types/memory";

export default function MemoryEntityCard({
  entity,
  onLedger,
  onReview,
}: {
  entity: MemoryEntityItem;
  onLedger?: (entity: MemoryEntityItem) => void;
  onReview?: (entity: MemoryEntityItem) => void;
}) {
  return (
    <div className="rounded-md border border-white/10 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-white">{entity.label}</h3>
          <p className="text-xs text-gray-500">{entity.domain_type}</p>
        </div>
        <span className="badge">{Math.round(entity.confidence * 100)}%</span>
      </div>
      <p className="mt-2 text-sm text-gray-400">{entity.lifecycle_state}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          href={`/memories/detail?id=${encodeURIComponent(entity.entity_id)}`}
          className="rounded-md border border-white/10 px-3 py-1.5 text-sm text-gray-100 hover:bg-white/10"
        >
          Details
        </Link>
        {onLedger && (
          <button
            type="button"
            onClick={() => onLedger(entity)}
            className="rounded-md border border-white/10 px-3 py-1.5 text-sm text-gray-100"
          >
            Ledger
          </button>
        )}
        {onReview && (
          <button
            type="button"
            onClick={() => onReview(entity)}
            className="rounded-md border border-white/10 px-3 py-1.5 text-sm text-gray-100"
          >
            Ask Review
          </button>
        )}
      </div>
    </div>
  );
}
