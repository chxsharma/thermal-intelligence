"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { formatWhen } from "@/types/domain";

export default function FacilitiesPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    apiGet("/api/facilities")
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  const items = data?.facilities || [];
  const current = items.find((x: any) => x.facility.id === selected) || items[0];

  if (error) return <Empty error={error} />;
  if (!data) return <p className="p-4 text-mist-400">Loading facilities…</p>;
  if (!items.length) return <p className="p-4 text-mist-400">No mapped industrial facilities in the current extract.</p>;

  return (
    <div className="mx-auto grid max-w-6xl gap-4 p-4 md:grid-cols-[280px_1fr]">
      <div className="border border-ink-600 bg-ink-900">
        {items.map((row: any) => (
          <button
            key={row.facility.id}
            type="button"
            onClick={() => setSelected(row.facility.id)}
            className="block w-full border-b border-ink-600 px-3 py-2 text-left hover:bg-ink-800"
          >
            <div className="text-sm">{row.facility.name}</div>
            <div className="font-mono text-[11px] text-mist-400">{row.facility.facility_type}</div>
          </button>
        ))}
      </div>
      {current && (
        <div className="border border-ink-600 bg-ink-900 p-4">
          <h1 className="text-lg">{current.facility.name}</h1>
          <p className="mt-1 font-mono text-[12px] text-mist-400">
            {current.facility.latitude.toFixed(4)}, {current.facility.longitude.toFixed(4)} · {current.facility.facility_type}
          </p>
          <p className="mt-3 border border-ink-600 px-3 py-2 text-sm text-mist-400">{current.language}</p>
          <h2 className="mt-4 font-mono text-[11px] uppercase tracking-wider text-teal-300">Nearby thermal activity</h2>
          <table className="mt-2 w-full text-left text-sm">
            <thead className="text-mist-400">
              <tr>
                <th className="py-1">Source</th>
                <th>Distance</th>
                <th>Class</th>
                <th>30d</th>
                <th>Last seen</th>
              </tr>
            </thead>
            <tbody>
              {current.nearby_sources.map((s: any) => (
                <tr key={s.cluster_id} className="border-t border-ink-600">
                  <td className="py-1">
                    <Link className="text-teal-300" href={`/sources?focus=${s.cluster_id}`}>
                      {s.cluster_id}
                    </Link>
                  </td>
                  <td>{Math.round(s.distance_m)} m</td>
                  <td>{s.classification}</td>
                  <td>{s.persistence_30d}</td>
                  <td>{formatWhen(s.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Empty({ error }: { error: string }) {
  return <p className="p-4 text-signal-red">Could not load facilities. {error}</p>;
}
