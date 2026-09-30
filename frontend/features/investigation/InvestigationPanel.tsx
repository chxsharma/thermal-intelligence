"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { CLASS_COLOR, classGlyph, formatMeters, formatWhen } from "@/types/domain";

const RECLASSIFY = [
  ["abnormal_industrial_thermal_event", "Abnormal Industrial Thermal Event"],
  ["persistent_industrial_thermal_source", "Persistent Industrial Thermal Source"],
  ["vegetation_natural_fire", "Vegetation / Natural Fire"],
  ["agricultural_burning", "Agricultural Burning"],
  ["other_unknown", "Other / Unknown"],
  ["insufficient_evidence", "Insufficient Evidence"],
] as const;

export function InvestigationPanel({
  sourceId,
  asOf,
  onClose,
  onReviewed,
}: {
  sourceId: string | null;
  asOf?: string | null;
  onClose?: () => void;
  onReviewed?: () => void;
}) {
  const [doc, setDoc] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [lineageOpen, setLineageOpen] = useState(false);
  const [note, setNote] = useState("");
  const [analyst, setAnalyst] = useState("analyst");
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [reclass, setReclass] = useState("insufficient_evidence");

  async function load(id: string) {
    setLoading(!doc || doc.summary?.id !== id);
    setError(null);
    try {
      const q = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
      setDoc(await apiGet(`/api/sources/${id}${q}`));
    } catch (err) {
      setError((err as Error).message);
      setDoc(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setActionMsg(null);
    if (sourceId) void load(sourceId);
    else setDoc(null);
  }, [sourceId, asOf]);

  const spark = useMemo(() => buildSpark(doc?.observations || []), [doc]);

  if (!sourceId) {
    return (
      <div className="flex h-full items-center justify-center bg-ink-900/95 px-5 text-center text-[13px] text-mist-400">
        Select a source. The inspector answers where, what, why, how confident, what changed over time, and what to do next.
      </div>
    );
  }
  if (loading) return <div className="bg-ink-900/95 p-4 text-sm text-mist-400">Loading investigation…</div>;
  if (error) return <div className="bg-ink-900/95 p-4 text-sm text-signal-red">Could not load source. {error}</div>;
  if (!doc) return null;

  const clf = doc.classification;
  const feat = doc.features;
  const summary = doc.summary;
  const nearestName = doc.nearby_facilities?.[0]?.name;
  const topSupport = clf.supporting_evidence?.[0];
  const topCounter = clf.counter_evidence?.[0];
  const recommended = clf.review_recommended
    ? `Review — ${clf.review_reasons.join("; ") || "incomplete or conflicting evidence"}`
    : "No system flag. Analyst may still override.";

  async function review(action: string, new_label?: string) {
    try {
      await apiPost(`/api/review/${sourceId}`, { action, analyst, note, new_label });
      setActionMsg(`Recorded ${action.replace("_", " ")}`);
      setNote("");
      if (sourceId) await load(sourceId);
      onReviewed?.();
    } catch (err) {
      setActionMsg((err as Error).message);
    }
  }

  return (
    <div className="h-full overflow-y-auto bg-ink-900/95">
      <div className="border-b border-ink-600 px-3 py-3">
        <div className="flex items-start justify-between gap-2">
          <div className="font-mono text-[10px] uppercase tracking-wider text-mist-400">Source / event</div>
          {onClose && (
            <button type="button" className="text-[12px] text-mist-400" onClick={onClose}>
              Close
            </button>
          )}
        </div>
        <div className="font-mono text-[13px] text-teal-300">{summary.id}</div>
        <div className="mt-2 flex items-center gap-2">
          <span className="px-1.5 py-0.5 font-mono text-[10px] text-ink-950" style={{ background: CLASS_COLOR[clf.label] }}>
            {classGlyph(clf.label)}
          </span>
          <div className="text-[15px] leading-tight break-words">{doc.classification_title}</div>
        </div>
        <div className="mt-2 font-mono text-[11px] uppercase tracking-wide">
          <span className="text-teal-300">{clf.confidence_band} confidence</span>
          <span className="mx-2 text-mist-500">·</span>
          <span>Priority {clf.priority}</span>
        </div>
        {clf.confidence_band === "LOW" || clf.confidence_band === "UNRESOLVED" ? (
          <p className="mt-1 text-[11px] text-[#c9a227]">
            Potentially important event, but insufficient evidence for certainty.
          </p>
        ) : null}
        <div className="mt-2 space-y-1 border-t border-ink-600 pt-2">
          <Fact k="Where" v={`${summary.centroid_lat.toFixed(4)}, ${summary.centroid_lon.toFixed(4)}`} />
          <Fact k="What" v={doc.classification_title} />
          <Fact k="Why" v={topSupport?.effect || "See supporting evidence"} />
          <Fact k="How confident" v={`${clf.confidence_band} · Priority ${clf.priority}`} />
        </div>
        <div className="mt-2 text-[12px]">
          <div className="font-mono text-[10px] uppercase text-mist-400">Spatial association</div>
          {feat.context_status === "available" && nearestName ? (
            <p className="break-words">
              Spatially associated with <span className="text-mist-100">{nearestName}</span>
              {feat.nearest_industrial_distance != null ? ` · ${formatMeters(feat.nearest_industrial_distance)}` : ""}. This does not establish causation.
            </p>
          ) : (
            <p className="text-mist-400">
              {feat.context_status === "not_found"
                ? "Mapped industrial context was searched and not found nearby."
                : "Industrial context is not available / unknown — absence is not evidence that no facility exists."}
            </p>
          )}
        </div>
        <p className="mt-2 text-[11px] text-mist-500">Evidence Engine reading. FIRMS detections are not ground truth.</p>
      </div>

      <div className="grid shrink-0 grid-cols-2 gap-px border-b border-ink-600 bg-ink-600">
        <div className="bg-ink-900 px-3 py-2">
          <div className="font-mono text-[10px] uppercase text-teal-300">Top supporting evidence</div>
          <p className="mt-1 text-[12px]">{topSupport ? `${topSupport.feature_name || ""} ${topSupport.feature_value ? `= ${topSupport.feature_value}` : ""}`.trim() : "None generated"}</p>
          {topSupport && <p className="mt-1 text-[11px] text-mist-400">{topSupport.statement}</p>}
        </div>
        <div className="bg-ink-900 px-3 py-2">
          <div className="font-mono text-[10px] uppercase text-[#c9a227]">Top counter-evidence</div>
          <p className="mt-1 text-[12px]">{topCounter ? `${topCounter.feature_name || ""} ${topCounter.feature_value ? `= ${topCounter.feature_value}` : ""}`.trim() : "None generated"}</p>
          {topCounter && <p className="mt-1 text-[11px] text-mist-400">{topCounter.statement}</p>}
        </div>
      </div>

      <div className="shrink-0 border-b border-ink-600 px-3 py-2">
        <div className="font-mono text-[10px] uppercase tracking-wider text-teal-300">Analyst action</div>
        <p className="mt-1 text-[12px]">Recommended: {recommended}</p>
        <p className="text-[11px] text-mist-400">System → Human → {doc.final_status}</p>
        <div className="mt-2 flex flex-wrap gap-1">
          <button type="button" onClick={() => review("confirm")} className="border border-ink-600 px-2 py-1 font-mono text-[10px] uppercase hover:border-teal-400">
            Confirm
          </button>
          <button type="button" onClick={() => review("reject")} className="border border-ink-600 px-2 py-1 font-mono text-[10px] uppercase hover:border-teal-400">
            Reject
          </button>
          <button type="button" onClick={() => review("mark_unresolved")} className="border border-ink-600 px-2 py-1 font-mono text-[10px] uppercase hover:border-teal-400">
            Mark unresolved
          </button>
          <button type="button" onClick={() => review("reclassify", reclass)} className="border border-ink-600 px-2 py-1 font-mono text-[10px] uppercase hover:border-teal-400">
            Reclassify
          </button>
        </div>
        <select value={reclass} onChange={(e) => setReclass(e.target.value)} className="mt-1 w-full border border-ink-600 bg-ink-950 px-1 py-1 text-[11px]">
          {RECLASSIFY.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
        {actionMsg && <p className="mt-1 text-[12px] text-teal-300">{actionMsg}</p>}
      </div>

      <div>
        <Section title="Temporal history">
          <Row k="First observed" v={formatWhen(summary.first_seen)} />
          <Row k="Last observed" v={formatWhen(summary.last_seen)} />
          <Row k="Active days" v={String(summary.active_days)} />
          <Row k="Detection count" v={String(summary.observation_count)} />
          <div className="mt-2">
            <div className="font-mono text-[10px] uppercase text-mist-400">Detections in view</div>
            <Sparkline values={spark} />
          </div>
          <input value={analyst} onChange={(e) => setAnalyst(e.target.value)} className="mt-2 w-full border border-ink-600 bg-ink-950 px-2 py-1 text-sm" placeholder="Analyst id" />
          <textarea value={note} onChange={(e) => setNote(e.target.value)} className="mt-1 w-full border border-ink-600 bg-ink-950 px-2 py-1 text-sm" rows={2} placeholder="Audit note" />
        </Section>
        <Section title="Supporting evidence">
          <EvidenceList items={clf.supporting_evidence} />
        </Section>
        <Section title="Counter-evidence">
          <EvidenceList items={clf.counter_evidence} empty="No counter-evidence items were generated from available features." />
          <div className="mt-3 font-mono text-[10px] uppercase text-mist-400">Why not?</div>
          <p className="mt-1 text-[12px]"><span className="text-mist-400">Wildfire — </span>{clf.why_not.wildfire}</p>
          <p className="mt-1 text-[12px]"><span className="text-mist-400">Agricultural burning — </span>{clf.why_not.agricultural_burning}</p>
          <p className="mt-1 text-[12px]"><span className="text-mist-400">Industrial source — </span>{clf.why_not.industrial_source}</p>
        </Section>
        <Section title="Context">
          <Row k="Coordinates" v={`${summary.centroid_lat.toFixed(4)}, ${summary.centroid_lon.toFixed(4)}`} />
          <Row k="Region" v={doc.scenario?.region || "Not labelled"} />
          <Row k="Context status" v={feat.context_status} />
          <Row k="Count ≤1 km" v={feat.industrial_count_1km == null ? "Unknown" : String(feat.industrial_count_1km)} />
        </Section>
        <Section title="Provenance">
          <Row k="Dataset" v={doc.lineage?.provenance?.source_dataset || "—"} />
          <Row k="Sensor" v={doc.lineage?.provenance?.sensor || "—"} />
          <button type="button" onClick={() => setLineageOpen((v) => !v)} className="mt-2 font-mono text-[11px] uppercase text-teal-300">
            {lineageOpen ? "Hide evidence lineage" : "View evidence lineage"}
          </button>
          {lineageOpen && (
            <ol className="mt-2 space-y-1 font-mono text-[11px]">
              {(doc.lineage?.nodes || []).map((n: any, i: number) => (
                <li key={n.id}>
                  {i + 1}. {n.label}
                </li>
              ))}
            </ol>
          )}
        </Section>
      </div>
    </div>
  );
}

function Sparkline({ values }: { values: number[] }) {
  if (!values.length) return <p className="text-[12px] text-mist-400">No detections in this time window.</p>;
  const max = Math.max(...values, 1);
  const w = 220;
  const h = 36;
  const step = values.length > 1 ? w / (values.length - 1) : w;
  const d = values.map((v, i) => `${i === 0 ? "M" : "L"} ${i * step} ${h - (v / max) * (h - 4) - 2}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="mt-1 w-full text-teal-300" aria-label="Detection sparkline">
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function buildSpark(observations: Array<{ acquired_at: string }>): number[] {
  if (!observations?.length) return [];
  const days = new Map<string, number>();
  for (const o of observations) {
    const day = o.acquired_at.slice(0, 10);
    days.set(day, (days.get(day) || 0) + 1);
  }
  return [...days.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([, n]) => n);
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-b border-ink-600 px-3 py-3">
      <h2 className="mb-2 font-mono text-[11px] uppercase tracking-wider text-teal-300">{title}</h2>
      {children}
    </section>
  );
}

function Fact({ k, v }: { k: string; v: string }) {
  return (
    <div className="py-0.5 text-[12px]">
      <div className="font-mono text-[10px] uppercase text-mist-400">{k}</div>
      <div className="break-words text-mist-100">{v}</div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3 py-0.5 text-[13px]">
      <span className="text-mist-400">{k}</span>
      <span className="text-right">{v}</span>
    </div>
  );
}

function EvidenceList({ items, empty }: { items: any[]; empty?: string }) {
  if (!items?.length) return <p className="text-[13px] text-mist-400">{empty || "None."}</p>;
  return (
    <ul className="mt-1 space-y-2">
      {items.map((item) => (
        <li key={item.code + item.statement} className="border border-ink-600 px-2 py-1.5 text-[12px]">
          <div className="font-mono text-[10px] uppercase text-mist-400">
            {item.feature || item.feature_name} {(item.actual_value || item.feature_value) ? `= ${item.actual_value || item.feature_value}` : ""}
          </div>
          {item.effect ? <div className="text-[11px] text-mist-400">{item.effect}</div> : null}
          {item.explanation || item.statement}
        </li>
      ))}
    </ul>
  );
}
