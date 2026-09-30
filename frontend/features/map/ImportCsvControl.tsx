"use client";

import { useState } from "react";
import { apiUpload } from "@/lib/api";

type Preview = {
  rows: number;
  columns: string[];
  parsed_observations: number;
  missing_required_fields: string[];
  missing_frp: number;
  date_range: string[] | null;
  geographic_extent: { min_lat: number | null; max_lat: number | null; min_lon: number | null; max_lon: number | null };
  validation_status: string;
  parse_error: string | null;
};

export function ImportCsvControl({ onIngested }: { onIngested: () => void }) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function validate(next: File) {
    setBusy(true);
    setError(null);
    try {
      const result = await apiUpload<{ preview: Preview }>("/api/ingest/csv/preview", next);
      setFile(next);
      setPreview(result.preview);
    } catch (err) {
      setPreview(null);
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function ingest() {
    if (!file || preview?.validation_status !== "valid") return;
    setBusy(true);
    setError(null);
    try {
      await apiUpload("/api/ingest/csv", file);
      setOpen(false);
      setFile(null);
      setPreview(null);
      onIngested();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="border border-ink-600 bg-ink-900/95 px-2 py-1 font-mono text-[10px] uppercase tracking-wide text-mist-100">
        Import FIRMS CSV
      </button>
      {open && (
        <div className="absolute inset-0 z-30 flex items-center justify-center bg-ink-950/70 p-4">
          <div className="w-full max-w-lg border border-ink-600 bg-ink-900 p-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="font-mono text-[11px] uppercase tracking-wider text-teal-300">Import FIRMS CSV</div>
                <p className="mt-1 text-[12px] text-mist-400">Validate before ingest. Existing demo observations are kept; accepted rows are added to the same pipeline.</p>
              </div>
              <button type="button" className="text-mist-400" onClick={() => setOpen(false)}>
                Close
              </button>
            </div>
            <input
              type="file"
              accept=".csv"
              className="mt-3 block w-full text-[12px]"
              onChange={(e) => e.target.files?.[0] && validate(e.target.files[0])}
            />
            {busy && <p className="mt-2 text-sm text-mist-400">Working…</p>}
            {error && <p className="mt-2 text-sm text-signal-red">{error}</p>}
            {preview && (
              <div className="mt-3 space-y-1 border border-ink-600 px-3 py-2 text-[12px]">
                <Row k="Validation" v={preview.validation_status} />
                <Row k="Rows" v={String(preview.rows)} />
                <Row k="Columns" v={preview.columns.join(", ") || "—"} />
                <Row k="Parsed observations" v={String(preview.parsed_observations)} />
                <Row k="Missing required fields" v={preview.missing_required_fields.join(", ") || "none"} />
                <Row k="Missing FRP" v={String(preview.missing_frp)} />
                <Row k="Date range" v={preview.date_range ? preview.date_range.map((d) => d.slice(0, 10)).join(" → ") : "—"} />
                <Row
                  k="Geographic extent"
                  v={
                    preview.geographic_extent.min_lat == null
                      ? "—"
                      : `${preview.geographic_extent.min_lat.toFixed(3)}, ${preview.geographic_extent.min_lon?.toFixed(3)} → ${preview.geographic_extent.max_lat?.toFixed(3)}, ${preview.geographic_extent.max_lon?.toFixed(3)}`
                  }
                />
                {preview.parse_error && <p className="text-signal-red">{preview.parse_error}</p>}
              </div>
            )}
            <div className="mt-3 flex justify-end gap-2">
              <button type="button" className="border border-ink-600 px-3 py-1 font-mono text-[11px] uppercase" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button
                type="button"
                disabled={!preview || preview.validation_status !== "valid" || busy}
                className="border border-teal-400 px-3 py-1 font-mono text-[11px] uppercase text-teal-300 disabled:opacity-40"
                onClick={() => void ingest()}
              >
                Ingest into pipeline
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-mist-400">{k}</span>
      <span className="max-w-[60%] text-right">{v}</span>
    </div>
  );
}
