"use client";

import { useEffect, useState } from "react";
import { apiGet, apiUpload } from "@/lib/api";

export default function HealthPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [upload, setUpload] = useState<string | null>(null);

  async function refresh() {
    try {
      setData(await apiGet("/api/health"));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function onFile(file: File) {
    try {
      const result = await apiUpload<any>("/api/ingest/csv", file);
      setUpload(JSON.stringify(result.preview, null, 2));
      await refresh();
    } catch (e) {
      setUpload((e as Error).message);
    }
  }

  if (error) {
    return (
      <div className="p-4">
        <p className="text-signal-red">API failure. {error}</p>
        <button type="button" className="mt-2 border border-ink-600 px-2 py-1 text-sm" onClick={() => void refresh()}>
          Retry
        </button>
      </div>
    );
  }
  if (!data) return <p className="p-4 text-mist-400">Loading data & model health…</p>;

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      <h1 className="font-mono text-[12px] uppercase tracking-wider text-mist-400">Data & model health</h1>
      <div className="grid gap-2 md:grid-cols-2">
        <Cell k="Operating mode" v={data.mode} />
        <Cell k="Data provider" v={`${data.data_provider.name}${data.data_provider.error ? " — error, fallback used" : ""}`} />
        <Cell k="Context provider" v={`${data.context_provider.name} (${data.context_provider.mode})`} />
        <Cell k="Imagery" v={data.imagery_provider.ready ? "configured" : "not configured"} />
        <Cell k="Observations" v={String(data.observation_count)} />
        <Cell k="Freshness" v={data.data_freshness || "—"} />
        <Cell k="Classifier" v={`${data.classifier_provider} ${data.classifier_version}`} />
        <Cell k="Feature schema" v={data.feature_schema_version} />
        <Cell k="Evaluation" v={data.evaluation_status} />
        <Cell k="API status" v={data.api_status} />
        <Cell k="Database URL scheme" v={data.database} />
        <Cell k="Last FIRMS ingest" v={data.last_firms_ingest_at || "—"} />
        <Cell k="Clusters" v={String(data.clustering_diagnostics?.cluster_count ?? "—")} />
      </div>
      {data.clustering_diagnostics && (
        <div className="border border-ink-600 bg-ink-900 p-3">
          <h2 className="font-mono text-[11px] uppercase text-mist-400">Clustering diagnostics</h2>
          <div className="mt-2 grid gap-2 md:grid-cols-3">
            <Cell k="Observations" v={String(data.clustering_diagnostics.observation_count)} />
            <Cell k="Clusters" v={String(data.clustering_diagnostics.cluster_count)} />
            <Cell k="Avg obs / cluster" v={String(data.clustering_diagnostics.average_observations_per_cluster)} />
            <Cell k="Largest cluster" v={String(data.clustering_diagnostics.largest_cluster_size)} />
            <Cell k="Single-obs clusters" v={String(data.clustering_diagnostics.single_observation_cluster_count)} />
            <Cell k="Multi-day clusters" v={String(data.clustering_diagnostics.multi_day_cluster_count)} />
            <Cell k="Span 7+ days" v={String(data.clustering_diagnostics.clusters_spanning_7d_plus)} />
            <Cell k="Span 14+ days" v={String(data.clustering_diagnostics.clusters_spanning_14d_plus)} />
            <Cell k="Span 30+ days" v={String(data.clustering_diagnostics.clusters_spanning_30d_plus)} />
            <Cell k="Median duration (h)" v={String(data.clustering_diagnostics.median_cluster_duration_hours ?? "—")} />
          </div>
        </div>
      )}
      {data.context_diagnostics && (
        <div className="border border-ink-600 bg-ink-900 p-3">
          <h2 className="font-mono text-[11px] uppercase text-mist-400">OSM context diagnostics</h2>
          <div className="mt-2 grid gap-2 md:grid-cols-3">
            <Cell k="Context provider" v={String(data.context_diagnostics.provider)} />
            <Cell k="With industrial context" v={String(data.context_diagnostics.clusters_with_industrial_context)} />
            <Cell k="Not found (search ran)" v={String(data.context_diagnostics.clusters_not_found)} />
            <Cell k="Not available" v={String(data.context_diagnostics.clusters_not_available)} />
            <Cell k="Provider failure" v={String(data.context_diagnostics.clusters_unavailable_due_to_provider_failure)} />
            <Cell k="Overpass queries" v={String(data.context_diagnostics.overpass_queries)} />
          </div>
          <p className="mt-2 text-[11px] text-mist-500">{data.context_diagnostics.note}</p>
        </div>
      )}
      {data.data_provider.error && (
        <div className="border border-signal-red px-3 py-2 text-sm text-signal-red">Provider error: {data.data_provider.error}</div>
      )}
      <div className="border border-ink-600 bg-ink-900 p-3">
        <h2 className="font-mono text-[11px] uppercase text-mist-400">FIRMS CSV ingest</h2>
        <input type="file" accept=".csv" className="mt-2 text-sm" onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} />
        {upload && <pre className="mt-2 overflow-auto text-[11px] text-mist-400">{upload}</pre>}
      </div>
    </div>
  );
}

function Cell({ k, v }: { k: string; v: string }) {
  return (
    <div className="border border-ink-600 bg-ink-900 px-3 py-2">
      <div className="font-mono text-[10px] uppercase text-mist-400">{k}</div>
      <div className="text-sm">{v}</div>
    </div>
  );
}
