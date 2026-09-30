"use client";

import { SourceCard } from "@/types/domain";
import { classGlyph, formatMeters, formatWhen, CLASS_COLOR } from "@/types/domain";
import { EMPTY_FILTERS, SourceFilters, filterSources } from "@/lib/filters";
import { cn } from "@/lib/api";

export function SourceExplorer({
  sources,
  selectedId,
  filters,
  onFilters,
  onSelect,
  compareIds,
  onToggleCompare,
}: {
  sources: SourceCard[];
  selectedId?: string | null;
  filters: SourceFilters;
  onFilters: (f: SourceFilters) => void;
  onSelect: (id: string) => void;
  compareIds?: string[];
  onToggleCompare?: (id: string) => void;
}) {
  const visible = filterSources(sources, filters);

  return (
    <div className="flex h-full flex-col bg-ink-900">
      <div className="border-b border-ink-600 px-3 py-2">
        <div className="font-mono text-[11px] uppercase tracking-wider text-mist-400">Source explorer</div>
        <input
          value={filters.q}
          onChange={(e) => onFilters({ ...filters, q: e.target.value })}
          placeholder="Search id, region, scenario"
          className="mt-2 w-full border border-ink-600 bg-ink-950 px-2 py-1 text-sm outline-none focus:border-teal-400"
        />
        <div className="mt-2 grid grid-cols-2 gap-1">
          <Select value={filters.classification} onChange={(v) => onFilters({ ...filters, classification: v })} options={CLASS_OPTIONS} />
          <Select value={filters.confidence} onChange={(v) => onFilters({ ...filters, confidence: v })} options={CONF_OPTIONS} />
          <Select value={filters.priority} onChange={(v) => onFilters({ ...filters, priority: v })} options={PRI_OPTIONS} />
          <Select value={filters.persistence} onChange={(v) => onFilters({ ...filters, persistence: v })} options={PERS_OPTIONS} />
          <Select value={filters.industrial} onChange={(v) => onFilters({ ...filters, industrial: v })} options={IND_OPTIONS} />
          <Select value={filters.sort} onChange={(v) => onFilters({ ...filters, sort: v })} options={SORT_OPTIONS} />
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {visible.length === 0 ? (
          <div className="px-3 py-8 text-center text-sm text-mist-400">No sources match these filters.</div>
        ) : (
          visible.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => onSelect(s.id)}
              className={cn(
                "block w-full border-b border-ink-600 px-3 py-2 text-left hover:bg-ink-800",
                selectedId === s.id && "bg-ink-800"
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-[11px] text-teal-300">{s.id}</span>
                <span
                  className="px-1.5 py-0.5 font-mono text-[10px] text-ink-950"
                  style={{ background: CLASS_COLOR[s.classification] }}
                >
                  {classGlyph(s.classification)}
                </span>
              </div>
              <div className="mt-0.5 text-[13px] text-mist-100">{s.classification_title}</div>
              <div className="mt-1 grid grid-cols-2 gap-x-2 text-[11px] text-mist-400">
                <div>Conf {s.confidence}</div>
                <div>Pri {s.priority}</div>
                <div>Obs {s.observation_count}</div>
                <div>{formatMeters(s.nearest_facility_m, s.context_status)}</div>
              </div>
              <div className="mt-1 text-[11px] text-mist-500">{formatWhen(s.last_observation)}</div>
              {onToggleCompare && (
                <span
                  role="checkbox"
                  aria-checked={compareIds?.includes(s.id)}
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleCompare(s.id);
                  }}
                  className="mt-1 inline-block font-mono text-[10px] uppercase text-teal-300"
                >
                  {compareIds?.includes(s.id) ? "In compare" : "Add to compare"}
                </span>
              )}
            </button>
          ))
        )}
      </div>
      <button
        type="button"
        className="border-t border-ink-600 px-3 py-1 text-left font-mono text-[10px] uppercase text-mist-400"
        onClick={() => onFilters(EMPTY_FILTERS)}
      >
        Reset filters · {visible.length} shown
      </button>
    </div>
  );
}

function Select({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="border border-ink-600 bg-ink-950 px-1 py-1 font-mono text-[10px] uppercase outline-none"
    >
      {options.map(([v, l]) => (
        <option key={v} value={v}>
          {l}
        </option>
      ))}
    </select>
  );
}

const CLASS_OPTIONS: [string, string][] = [
  ["", "All classes"],
  ["abnormal_industrial_thermal_event", "Abnormal industrial"],
  ["persistent_industrial_thermal_source", "Persistent industrial"],
  ["vegetation_natural_fire", "Vegetation"],
  ["agricultural_burning", "Agricultural"],
  ["other_unknown", "Other"],
  ["insufficient_evidence", "Insufficient"],
];
const CONF_OPTIONS: [string, string][] = [
  ["", "All confidence"],
  ["HIGH", "High"],
  ["MEDIUM", "Medium"],
  ["LOW", "Low"],
  ["UNRESOLVED", "Unresolved"],
];
const PRI_OPTIONS: [string, string][] = [
  ["", "All priority"],
  ["High", "High"],
  ["Medium", "Medium"],
  ["Low", "Low"],
];
const PERS_OPTIONS: [string, string][] = [
  ["", "Any persistence"],
  ["persistent", "Persistent"],
  ["short", "Short"],
];
const IND_OPTIONS: [string, string][] = [
  ["", "Any industrial ctx"],
  ["associated", "Associated ≤1km"],
  ["not_found", "Not found"],
  ["not_available", "Not available"],
];
const SORT_OPTIONS: [string, string][] = [
  ["priority", "Sort: priority"],
  ["persistence", "Sort: persistence"],
  ["latest", "Sort: latest"],
  ["confidence", "Sort: confidence"],
];
