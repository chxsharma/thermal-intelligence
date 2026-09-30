"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<any[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    apiGet<{ alerts: any[] }>("/api/alerts")
      .then((d) => setAlerts(d.alerts))
      .catch((e: Error) => setError(e.message));
  }, []);
  if (error) return <p className="p-4 text-signal-red">{error}</p>;
  if (!alerts) return <p className="p-4 text-mist-400">Loading alerts…</p>;
  if (!alerts.length) return <p className="p-4 text-mist-400">No alerts in the current snapshot.</p>;
  return (
    <div className="mx-auto max-w-4xl p-4">
      <h1 className="font-mono text-[12px] uppercase tracking-wider text-mist-400">Alert center</h1>
      <div className="mt-3 space-y-2">
        {alerts.map((a) => (
          <Link key={a.id} href="/" className="block border border-ink-600 bg-ink-900 px-3 py-3 hover:border-teal-400">
            <div className="flex justify-between font-mono text-[11px] uppercase text-mist-400">
              <span>{a.kind}</span>
              <span>Priority {a.priority}</span>
            </div>
            <div className="mt-1">{a.title}</div>
            <p className="mt-1 text-sm text-mist-400">{a.body}</p>
            <div className="mt-2 font-mono text-[11px] text-teal-300">Investigate {a.cluster_id}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
