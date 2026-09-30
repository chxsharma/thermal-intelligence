"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiGet } from "@/lib/api";
import { formatMeters, formatWhen } from "@/types/domain";
import { Suspense } from "react";

function CompareInner() {
  const params = useSearchParams();
  const [ids, setIds] = useState(params.get("ids") || "");
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const query = useMemo(() => ids.split(",").map((s) => s.trim()).filter(Boolean), [ids]);

  async function load() {
    if (query.length < 2) {
      setError("Enter at least two source IDs.");
      return;
    }
    setError(null);
    try {
      setData(await apiGet(`/api/compare?ids=${query.join(",")}`));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    const initialIds = params.get("ids")?.split(",").map((s) => s.trim()).filter(Boolean) || [];
    if (initialIds.length >= 2) {
      setError(null);
      void apiGet(`/api/compare?ids=${initialIds.join(",")}`)
        .then((res) => setData(res))
        .catch((e) => setError((e as Error).message));
    }
  }, [params]);

  return (
    <div className="p-4">
      <h1 className="font-mono text-[12px] uppercase tracking-wider text-mist-400">Compare sources</h1>
      <div className="mt-2 flex gap-2">
        <input value={ids} onChange={(e) => setIds(e.target.value)} className="w-full max-w-xl border border-ink-600 bg-ink-900 px-2 py-1 text-sm" placeholder="SRC-…,SRC-…" />
        <button type="button" onClick={load} className="border border-ink-600 px-3 font-mono text-[11px] uppercase">
          Compare
        </button>
      </div>
      {error && <p className="mt-3 text-sm text-signal-red">{error}</p>}
      {data && (
        <div className="mt-4 overflow-auto">
          <table className="w-full min-w-[800px] text-left text-sm">
            <thead>
              <tr className="text-mist-400">
                <th className="p-2">Field</th>
                {data.sources.map((s: any) => (
                  <th key={s.summary.id} className="p-2 font-mono text-teal-300">
                    {s.summary.id}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows(data.sources).map((row) => (
                <tr key={row.label} className="border-t border-ink-600">
                  <td className="p-2 text-mist-400">{row.label}</td>
                  {row.values.map((v, i) => (
                    <td key={i} className="p-2">
                      {v}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function rows(sources: any[]) {
  return [
    { label: "Classification", values: sources.map((s) => s.classification_title) },
    { label: "Confidence", values: sources.map((s) => s.classification.confidence_band) },
    { label: "Priority", values: sources.map((s) => s.classification.priority) },
    { label: "Persistence 30d", values: sources.map((s) => String(s.summary.persistence_30d)) },
    { label: "Industrial distance", values: sources.map((s) => formatMeters(s.features.nearest_industrial_distance, s.features.context_status)) },
    { label: "Mean FRP", values: sources.map((s) => (s.features.frp == null ? "not available" : s.features.frp.toFixed(1))) },
    { label: "Land context", values: sources.map((s) => s.features.land_context || "unknown") },
    { label: "First / last", values: sources.map((s) => `${formatWhen(s.summary.first_seen)} → ${formatWhen(s.summary.last_seen)}`) },
    { label: "Top evidence", values: sources.map((s) => s.classification.supporting_evidence[0]?.statement || "—") },
  ];
}

export default function ComparePage() {
  return (
    <Suspense fallback={<p className="p-4 text-mist-400">Loading compare…</p>}>
      <CompareInner />
    </Suspense>
  );
}
