"use client";

import { formatWhen } from "@/types/domain";
import { cn } from "@/lib/api";

export function ReplayControls({
  start,
  end,
  value,
  playing,
  speed,
  onChange,
  onPlay,
  onPause,
  onReset,
  onSpeed,
}: {
  start: string;
  end: string;
  value: string;
  playing: boolean;
  speed: number;
  onChange: (iso: string) => void;
  onPlay: () => void;
  onPause: () => void;
  onReset: () => void;
  onSpeed: (n: number) => void;
}) {
  const t0 = new Date(start).getTime();
  const t1 = new Date(end).getTime();
  const cur = new Date(value).getTime();

  return (
    <div className="pointer-events-auto w-full max-w-3xl border border-ink-600 bg-ink-900/95 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={playing ? onPause : onPlay} className="border border-ink-600 px-2 py-1 font-mono text-[11px] uppercase">
          {playing ? "Pause" : "Play"}
        </button>
        <button type="button" onClick={onReset} className="border border-ink-600 px-2 py-1 font-mono text-[11px] uppercase">
          Reset
        </button>
        <label className="font-mono text-[11px] text-mist-400">
          Speed
          <select value={speed} onChange={(e) => onSpeed(Number(e.target.value))} className="ml-1 border border-ink-600 bg-ink-950 px-1">
            <option value={1}>1×</option>
            <option value={2}>2×</option>
            <option value={4}>4×</option>
            <option value={8}>8×</option>
          </select>
        </label>
        <div className="font-mono text-[11px] text-teal-300">{formatWhen(value)}</div>
        <div className={cn("ml-auto font-mono text-[10px] uppercase text-mist-400")}>
          {new Date(start).toISOString().slice(0, 10)} — {new Date(end).toISOString().slice(0, 10)}
        </div>
      </div>
      <input
        type="range"
        min={t0}
        max={t1}
        value={Number.isFinite(cur) ? cur : t0}
        onChange={(e) => onChange(new Date(Number(e.target.value)).toISOString())}
        className="mt-2 w-full accent-teal-400"
      />
    </div>
  );
}
