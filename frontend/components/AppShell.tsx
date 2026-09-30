"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { apiGet, cn } from "@/lib/api";

const NAV = [
  ["Overview", "/"],
  ["Sources", "/sources"],
  ["Facilities", "/facilities"],
  ["Review", "/review"],
  ["Alerts", "/alerts"],
  ["Compare", "/compare"],
  ["Analytics", "/analytics"],
  ["Health", "/health"],
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [mode, setMode] = useState("…");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () => {
      apiGet<{ mode: string }>("/api/status")
        .then((s) => {
          setMode(s.mode);
          setError(null);
        })
        .catch((err: Error) => setError(err.message));
    };
    load();
    window.addEventListener("thermal-status", load);
    return () => window.removeEventListener("thermal-status", load);
  }, [path]);

  const live = mode.startsWith("LIVE");

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="shrink-0 border-b border-ink-600 bg-ink-900">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-1.5">
          <div className="font-mono text-[12px] tracking-[0.16em] text-mist-100">THERMAL // INTELLIGENCE</div>
          <span className={cn("border px-1.5 py-0.5 font-mono text-[10px] uppercase", live ? "border-signal-green text-signal-green" : "border-teal-400 text-teal-300")}>
            {live ? "LIVE NASA FIRMS" : mode === "…" ? "…" : "DEMO REPLAY"}
          </span>
          <span className="border border-ink-600 px-1.5 py-0.5 font-mono text-[10px] uppercase text-mist-400">Evidence Engine</span>
          <nav className="flex flex-wrap gap-0.5">
            {NAV.map(([label, href]) => {
              const active = href === "/" ? path === "/" : path.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn("px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide", active ? "bg-ink-700 text-teal-300" : "text-mist-400 hover:text-mist-100")}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto text-[11px] text-mist-500">
            {error ? <span className="text-signal-red">API unavailable</span> : "FIRMS ≠ ground truth · proximity ≠ causation"}
          </div>
        </div>
      </header>
      <main className="min-h-0 flex-1 bg-ink-950">{children}</main>
    </div>
  );
}
