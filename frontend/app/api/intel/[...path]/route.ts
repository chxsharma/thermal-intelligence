import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const TOKEN = process.env.ANALYST_WRITE_TOKEN || "dev-review-token";

async function forward(req: NextRequest, path: string[]) {
  const search = req.nextUrl.search;
  const target = `${BACKEND}/${path.join("/")}${search}`;
  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (req.method !== "GET") headers.set("X-Analyst-Token", TOKEN);
  const init: RequestInit = { method: req.method, headers };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = contentType?.includes("multipart/form-data") ? await req.formData() : await req.arrayBuffer();
  }
  const res = await fetch(target, init);
  const body = await res.arrayBuffer();
  return new NextResponse(body, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") || "application/json" },
  });
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path);
}

export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path);
}
