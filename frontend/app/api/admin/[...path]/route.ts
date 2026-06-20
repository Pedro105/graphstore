// Catch-all proxy for the operator admin API. The browser's /admin pages call
// /api/admin/<...> with the ADMIN_TOKEN in the Authorization header; this
// handler forwards each request verbatim to the FastAPI /v1/admin/<...>
// endpoint, carrying that header through. Keeping the backend base URL
// server-side is the only reason this hop exists -- the admin token itself is
// the operator's and is supposed to transit here.

import type { NextRequest } from "next/server";

import { forwardAdminToFastapi, relayResponse } from "@/lib/api/fastapi";

async function proxy(
  req: NextRequest,
  path: string[],
  method: "GET" | "DELETE",
): Promise<Response> {
  const search = new URL(req.url).search;
  const upstream = await forwardAdminToFastapi(
    `/v1/admin/${path.join("/")}${search}`,
    req.headers.get("authorization"),
    { method },
  );
  return relayResponse(upstream);
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await params;
  return proxy(req, path, "GET");
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await params;
  return proxy(req, path, "DELETE");
}
