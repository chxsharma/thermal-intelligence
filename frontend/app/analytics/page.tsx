"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function AnalyticsPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    apiGet("/api/analytics")
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);
  if (error) return <p className="p-4 text-signal-red">{error}</p>;
  if (!data) return <p className="p-4 text-mist-400">Loading analytics…</p>;

  const classData = Object.entries(data.classification_distribution || {}).map(([name, value]) => ({ name, value }));
  const confData = Object.entries(data.confidence_distribution || {}).map(([name, value]) => ({ name, value }));
  const persist = Object.entries(data.persistence_distribution || {}).map(([name, value]) => ({ name, value }));

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4">
      <h1 className="font-mono text-[12px] uppercase tracking-wider text-mist-400">Analytics</h1>
      <div className="grid gap-4 md:grid-cols-2">
        <ChartCard title="Classification distribution" rows={classData} />
        <ChartCard title="Confidence distribution" rows={confData} />
        <ChartCard title="Persistence (active days)" rows={persist} />
        <div className="border border-ink-600 bg-ink-900 p-3">
          <h2 className="font-mono text-[11px] uppercase text-mist-400">Industrial-context association</h2>
          <pre className="mt-2 text-sm">{JSON.stringify(data.industrial_context_association, null, 2)}</pre>
          <p className="mt-2 text-[12px] text-mist-400">Review queue volume: {data.review_queue_volume}</p>
        </div>
      </div>
      <div className="border border-ink-600 bg-ink-900 p-3">
        <h2 className="font-mono text-[11px] uppercase text-mist-400">Temporal detections</h2>
        <div className="h-48">
          <ResponsiveContainer>
            <BarChart data={data.temporal_trends}>
              <CartesianGrid stroke="#2a323b" />
              <XAxis dataKey="date" hide />
              <YAxis stroke="#8b98a5" />
              <Tooltip contentStyle={{ background: "#171b20", border: "1px solid #2a323b" }} />
              <Bar dataKey="observations" fill="#5fb3a8" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="border border-ink-600 bg-ink-900 p-3">
        <h2 className="font-mono text-[11px] uppercase text-mist-400">Regional source density</h2>
        <table className="mt-2 w-full text-left text-sm">
          <thead className="text-mist-400">
            <tr>
              <th>Source</th>
              <th>Region</th>
              <th>Obs</th>
            </tr>
          </thead>
          <tbody>
            {data.regional_source_density.map((r: any) => (
              <tr key={r.id} className="border-t border-ink-600">
                <td className="py-1 font-mono text-[12px]">{r.id}</td>
                <td>{r.region || "unlabelled"}</td>
                <td>{r.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border border-ink-600 bg-ink-900 p-4">
        <h2 className="font-mono text-[11px] uppercase text-mist-400">Held-out evaluation</h2>
        <p className="mt-2 text-lg">Evaluation not yet performed.</p>
        <p className="mt-1 text-sm text-mist-400">
          Precision, recall, F1, confusion matrix, and per-class scores are withheld until labelled validation data exists. No placeholder metrics are shown.
        </p>
      </div>
    </div>
  );
}

function ChartCard({ title, rows }: { title: string; rows: { name: string; value: unknown }[] }) {
  return (
    <div className="border border-ink-600 bg-ink-900 p-3">
      <h2 className="font-mono text-[11px] uppercase text-mist-400">{title}</h2>
      <div className="h-44">
        <ResponsiveContainer>
          <BarChart data={rows} layout="vertical" margin={{ left: 24 }}>
            <CartesianGrid stroke="#2a323b" />
            <XAxis type="number" stroke="#8b98a5" allowDecimals={false} />
            <YAxis type="category" dataKey="name" width={120} stroke="#8b98a5" tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#171b20", border: "1px solid #2a323b" }} />
            <Bar dataKey="value" fill="#5fb3a8" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
