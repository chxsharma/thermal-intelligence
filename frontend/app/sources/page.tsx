"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { SourceExplorer } from "@/features/sources/SourceExplorer";
import { InvestigationPanel } from "@/features/investigation/InvestigationPanel";
import { apiGet, apiUpload } from "@/lib/api";
import { EMPTY_FILTERS, SourceFilters } from "@/lib/filters";
import { SourceCard } from "@/types/domain";

export default function SourcesPage() {
  const [sources, setSources] = useState<SourceCard[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [filters, setFilters] = useState<SourceFilters>(EMPTY_FILTERS);
  const [compare, setCompare] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  useEffect(() => {
    apiGet<{ sources: SourceCard[] }>("/api/sources")
      .then((d) => {
        setSources(d.sources);
        setSelected(d.sources[0]?.id ?? null);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  async function onFile(file: File) {
    setUploadMsg("Validating…");
    try {
      const result = await apiUpload<{ preview: { rows: number; parsed_observations: number; date_range: string[] } }>("/api/ingest/csv", file);
      setUploadMsg(`Ingested ${result.preview.parsed_observations} observations from ${result.preview.rows} CSV rows.`);
      const d = await apiGet<{ sources: SourceCard[] }>("/api/sources");
      setSources(d.sources);
    } catch (e) {
      setUploadMsg((e as Error).message);
    }
  }

  return (
    <div className="flex h-[calc(100vh-108px)]">
      <div className="w-[340px] border-r border-ink-600">
        <div className="border-b border-ink-600 px-3 py-2 text-[12px] text-mist-400">
          Upload a FIRMS CSV to run the same pipeline. Columns are validated; unknown fields are ignored.
          <input
            type="file"
            accept=".csv"
            className="mt-2 block w-full text-[11px]"
            onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
          />
          {uploadMsg && <div className="mt-1 text-teal-300">{uploadMsg}</div>}
          {error && <div className="text-signal-red">{error}</div>}
        </div>
        <div className="h-[calc(100%-88px)]">
          <SourceExplorer
            sources={sources}
            selectedId={selected}
            filters={filters}
            onFilters={setFilters}
            onSelect={setSelected}
            compareIds={compare}
            onToggleCompare={(id) =>
              setCompare((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id].slice(0, 4)))
            }
          />
        </div>
      </div>
      <div className="min-w-0 flex-1">
        <InvestigationPanel sourceId={selected} />
      </div>
      {compare.length >= 2 && (
        <Link href={`/compare?ids=${compare.join(",")}`} className="fixed bottom-4 right-4 border border-teal-400 bg-ink-900 px-3 py-2 font-mono text-[11px] uppercase text-teal-300">
          Compare {compare.length} sources
        </Link>
      )}
    </div>
  );
}
