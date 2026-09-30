import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

function endpoint(path: string): string {
  if (typeof window === "undefined") {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    return `${base}${path}`;
  }
  return `/api/intel${path}`;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(endpoint(path), { cache: "no-store" });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(endpoint(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const data = new FormData();
  data.append("file", file);
  const res = await fetch(endpoint(path), { method: "POST", body: data });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Upload failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}
