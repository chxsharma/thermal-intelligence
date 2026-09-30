"use client";

import { useCallback, useEffect, useState } from "react";
import { IntelligenceMap } from "@/features/map/IntelligenceMap";
import { ImportCsvControl } from "@/features/map/ImportCsvControl";
import { SourceExplorer } from "@/features/sources/SourceExplorer";
import { InvestigationPanel } from "@/features/investigation/InvestigationPanel";
import { ReplayControls } from "@/features/timeline/ReplayControls";
import { apiGet, apiPost } from "@/lib/api";
import { EMPTY_FILTERS, SourceFilters } from "@/lib/filters";
import { CLASS_COLOR, MapPayload, SourceCard, classGlyph } from "@/types/domain";

const DEFAULT_LAYERS = {
  observations: true,
  clusters: true,
  facilities: true,
  associationRing: true,
  selectedFootprint: true,
};

export function Workspace({ replay: _ignored = true }: { replay?: boolean }) {
  const [mapData, setMapData] = useState<MapPayload | null>(null);
  const [sources, setSources] = useState<SourceCard[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [filters, setFilters] = useState<SourceFilters>(EMPTY_FILTERS);
  const [error, setError] = useState<string | null>(null);
  const [layers, setLayers] = useState(DEFAULT_LAYERS);
  const [asOf, setAsOf] = useState<string | null>(null);
  const [range, setRange] = useState<{ start: string; end: string } | null>(null);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2);
  const [basemap, setBasemap] = useState<"osm" | "graphite">("osm");
  const [showSources, setShowSources] = useState(true);
  const [showCase, setShowCase] = useState(true);
  const [reloadEpoch, setReloadEpoch] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  const loadStatic = useCallback((resetWindow = false) => {
    Promise.all([
      apiGet<{ sources: SourceCard[] }>("/api/sources"),
      apiGet<{ start: string; end: string }>("/api/replay/range"),
    ])
      .then(([s, r]) => {
        setSources(s.sources);
        setRange(r);
        setAsOf((prev) => (resetWindow || !prev ? r.end : prev));
        setSelected((prev) => {
          if (!resetWindow && prev) return prev;
          const preferred = s.sources.find((item) => item.id === "SRC-A4964848");
          return preferred?.id || s.sources[0]?.id || null;
        });
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const refreshFirms = useCallback(async () => {
    setRefreshing(true);
    try {
      await apiPost("/api/ingest/firms/refresh", {});
      window.dispatchEvent(new Event("thermal-status"));
      loadStatic(true);
      setReloadEpoch((n) => n + 1);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRefreshing(false);
    }
  }, [loadStatic]);

  useEffect(() => {
    loadStatic();
  }, [loadStatic]);

  useEffect(() => {
    const q = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
    apiGet<MapPayload>(`/api/map${q}`)
      .then(setMapData)
      .catch((err: Error) => setError(err.message));
  }, [asOf, reloadEpoch]);

  useEffect(() => {
    if (!playing || !range || !asOf) return;
    const t1 = new Date(range.end).getTime();
    const t0 = new Date(range.start).getTime();
    const id = window.setInterval(() => {
      setAsOf((prev) => {
        const cur = new Date(prev || range.start).getTime();
        const next = cur + 12 * 3600 * 1000 * speed;
        if (next >= t1) {
          setPlaying(false);
          return range.end;
        }
        return new Date(Math.max(t0, next)).toISOString();
      });
    }, 400);
    return () => window.clearInterval(id);
  }, [playing, range, speed, asOf]);

  const metrics = mapData?.metrics;

  return (
    <div className="relative h-full">
      <IntelligenceMap data={mapData} selectedId={selected} onSelect={setSelected} layers={layers} basemap={basemap} />

      <div className="pointer-events-none absolute inset-0">
        <div className="pointer-events-auto absolute left-3 right-3 top-3 flex flex-wrap items-center gap-2">
          <div className="flex flex-wrap gap-x-3 gap-y-1 border border-ink-600 bg-ink-900/95 px-3 py-1.5 font-mono text-[11px]">
            <span className="text-mist-400">Obs {metrics?.active_observations ?? "—"}</span>
            <span className="text-mist-400">Clusters {metrics?.source_clusters ?? "—"}</span>
            <span className="text-mist-400">Reviews {metrics?.priority_reviews ?? "—"}</span>
            <span className="text-mist-400">Fresh {metrics?.data_freshness ? metrics.data_freshness.slice(0, 10) : "—"}</span>
            <span className="text-mist-400">FIRMS ingest {mapData?.last_firms_ingest_at ? mapData.last_firms_ingest_at.replace("T", " ").slice(0, 19) + "Z" : "—"}</span>
          </div>
          <button type="button" className="border border-ink-600 bg-ink-900/95 px-2 py-1 font-mono text-[10px] uppercase" onClick={() => setShowSources((v) => !v)}>
            {showSources ? "Hide sources" : "Sources"}
          </button>
          <button type="button" className="border border-ink-600 bg-ink-900/95 px-2 py-1 font-mono text-[10px] uppercase" onClick={() => setShowCase((v) => !v)}>
            {showCase ? "Hide case" : "Case"}
          </button>
          <select value={basemap} onChange={(e) => setBasemap(e.target.value as "osm" | "graphite")} className="border border-ink-600 bg-ink-900/95 px-2 py-1 font-mono text-[10px] uppercase">
            <option value="osm">Basemap: OpenStreetMap</option>
            <option value="graphite">Basemap: OSM (FR)</option>
          </select>
          <button type="button" className="border border-ink-600 bg-ink-900/95 px-2 py-1 font-mono text-[10px] uppercase disabled:opacity-50" onClick={() => void refreshFirms()} disabled={refreshing}>
            {refreshing ? "Refreshing FIRMS…" : "Refresh FIRMS"}
          </button>
          <ImportCsvControl
            onIngested={() => {
              loadStatic();
              setReloadEpoch((n) => n + 1);
            }}
          />
        </div>

        {error && <div className="pointer-events-auto absolute left-3 top-14 max-w-md bg-signal-red/15 px-3 py-2 text-sm text-signal-red">{error}</div>}

        {showSources && (
          <aside className="pointer-events-auto absolute bottom-28 left-3 top-14 z-20 w-[280px] overflow-hidden border border-ink-600">
            <SourceExplorer sources={sources} selectedId={selected} filters={filters} onFilters={setFilters} onSelect={setSelected} />
          </aside>
        )}

        {showCase && (
          <aside className="pointer-events-auto absolute bottom-28 right-3 top-14 z-20 w-[380px] overflow-hidden border border-ink-600">
            <InvestigationPanel sourceId={selected} asOf={asOf} onReviewed={loadStatic} />
          </aside>
        )}

        <div className="pointer-events-none absolute bottom-3 left-[304px] right-[404px] z-20 flex justify-center">
          {range && asOf && (
            <ReplayControls
              start={range.start}
              end={range.end}
              value={asOf}
              playing={playing}
              speed={speed}
              onChange={setAsOf}
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onReset={() => {
                setPlaying(false);
                setAsOf(range.start);
              }}
              onSpeed={setSpeed}
            />
          )}
        </div>

        <div className="pointer-events-auto absolute bottom-28 left-[304px] z-10 max-w-[220px] border border-ink-600 bg-ink-900/95 p-2 text-[11px]">
          <div className="font-mono text-[10px] uppercase text-mist-400">Legend</div>
          <div className="mt-1 space-y-0.5">
            {Object.entries(CLASS_COLOR).map(([k, color]) => (
              <div key={k} className="flex items-center gap-2">
                <span className="h-2 w-2" style={{ background: color }} />
                <span>{classGlyph(k)}</span>
              </div>
            ))}
            <div className="pt-1 text-mist-400">Stroke = confidence band. Ring = 1 km association window for the selected source only. Footprint = observation locations, not a fire perimeter.</div>
          </div>
          <label className="mt-2 flex items-center gap-2">
            <input type="checkbox" checked={layers.observations} onChange={(e) => setLayers({ ...layers, observations: e.target.checked })} />
            Observations
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={layers.clusters} onChange={(e) => setLayers({ ...layers, clusters: e.target.checked })} />
            Source clusters
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={layers.facilities} onChange={(e) => setLayers({ ...layers, facilities: e.target.checked })} />
            Nearby facilities
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={layers.associationRing} onChange={(e) => setLayers({ ...layers, associationRing: e.target.checked })} />
            1 km association ring
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={layers.selectedFootprint} onChange={(e) => setLayers({ ...layers, selectedFootprint: e.target.checked })} />
            Selected footprint
          </label>
        </div>
      </div>
    </div>
  );
}
