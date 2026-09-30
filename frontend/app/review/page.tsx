"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { InvestigationPanel } from "@/features/investigation/InvestigationPanel";
import { apiGet } from "@/lib/api";

export default function ReviewPage() {
  const [data, setData] = useState<any>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet("/api/review")
      .then((d: any) => {
        setData(d);
        setSelected(d.queue[0]?.cluster_id ?? null);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p className="p-4 text-signal-red">{error}</p>;
  if (!data) return <p className="p-4 text-mist-400">Loading review queue…</p>;

  return (
    <div className="flex h-[calc(100vh-108px)]">
      <div className="w-[360px] overflow-auto border-r border-ink-600 bg-ink-900">
        <div className="border-b border-ink-600 px-3 py-2 font-mono text-[11px] uppercase text-mist-400">
          Analyst review queue · {data.queue.length}
        </div>
        {data.queue.length === 0 && <p className="p-3 text-sm text-mist-400">No review-flagged sources in the current snapshot.</p>}
        {data.queue.map((item: any) => (
          <button
            key={item.cluster_id}
            type="button"
            onClick={() => setSelected(item.cluster_id)}
            className="block w-full border-b border-ink-600 px-3 py-2 text-left hover:bg-ink-800"
          >
            <div className="font-mono text-[11px] text-teal-300">{item.cluster_id}</div>
            <div className="text-sm">{item.classification_title}</div>
            <div className="text-[11px] text-mist-400">
              {item.confidence} · {item.priority} · {item.review_reasons.join(", ")}
            </div>
            <div className="mt-1 font-mono text-[10px] uppercase text-mist-500">
              System recommendation → Human review → {item.final_status}
            </div>
          </button>
        ))}
        <div className="px-3 py-3">
          <div className="font-mono text-[10px] uppercase text-mist-400">Audit trail</div>
          {data.history.length === 0 && <p className="text-[12px] text-mist-500">No analyst actions yet.</p>}
          {data.history.map((h: any) => (
            <div key={h.id} className="mt-1 text-[12px] text-mist-400">
              {h.created_at.slice(0, 16)} · {h.analyst} · {h.action} · {h.cluster_id}
            </div>
          ))}
        </div>
      </div>
      <div className="flex-1">
        {selected ? <InvestigationPanel sourceId={selected} /> : <p className="p-4 text-mist-400">Select a review case.</p>}
        {selected && (
          <div className="border-t border-ink-600 px-3 py-2 text-[12px]">
            <Link className="text-teal-300" href="/">
              Open on map
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
