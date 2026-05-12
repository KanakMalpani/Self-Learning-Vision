"use client";

import type { MemoryReport } from "@/types/memory";
import { useMemo } from "react";

interface Props {
  memory_report?: MemoryReport;
}

export default function Corkboard({ memory_report }: Props) {
  const nodes = useMemo(() => {
    const facts = memory_report?.key_facts || [];
    const timeline = memory_report?.timeline || [];
    return [
      ...facts.map((fact, idx) => ({ id: `fact-${idx}`, label: fact.title, accent: true })),
      ...timeline.map((item, idx) => ({ id: `time-${idx}`, label: item.title, accent: false }))
    ];
  }, [memory_report]);

  const connections = useMemo(() => {
    const lines: Array<[string, string]> = [];
    for (let i = 0; i < nodes.length - 1; i++) {
      lines.push([nodes[i].id, nodes[i + 1].id]);
    }
    return lines;
  }, [nodes]);

  return (
    <div className="relative card p-4 h-full">
      <p className="font-semibold mb-3">Memory Map</p>
      {!memory_report && <p className="text-sm text-gray-500">Run local recognition to populate the map.</p>}
      <div className="relative grid grid-cols-1 md:grid-cols-2 gap-4 min-h-[280px]">
        {nodes.map((node, idx) => (
          <div key={node.id} className="relative">
            <div className={`p-4 rounded-lg border ${node.accent ? "border-board-accent" : "border-white/10"} bg-black/30 shadow-card`}>
              <p className="text-sm text-gray-400">{node.accent ? "Fact" : "Event"} {idx + 1}</p>
              <p className="font-semibold text-gray-100">{node.label}</p>
            </div>
          </div>
        ))}
        <svg className="absolute inset-0 pointer-events-none" aria-hidden>
          {connections.map((line, idx) => {
            const start = idx;
            const end = idx + 1;
            const colCount = 2;
            const startCol = start % colCount;
            const endCol = end % colCount;
            const startRow = Math.floor(start / colCount);
            const endRow = Math.floor(end / colCount);
            const x1 = startCol === 0 ? 25 : 75;
            const x2 = endCol === 0 ? 25 : 75;
            const y1 = startRow * 100 + 30;
            const y2 = endRow * 100 + 30;
            return (
              <line
                key={`${line[0]}-${line[1]}`}
                x1={`${x1}%`}
                y1={y1}
                x2={`${x2}%`}
                y2={y2}
                stroke="rgba(240, 198, 116, 0.5)"
                strokeWidth="2"
                strokeDasharray="4 4"
              />
            );
          })}
        </svg>
      </div>
    </div>
  );
}

