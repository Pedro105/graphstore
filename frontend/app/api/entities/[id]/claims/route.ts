import type { NextRequest } from "next/server";

import { forwardToFastapi, relayResponse } from "@/lib/api/fastapi";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
): Promise<Response> {
  // tenant is derived server-side from the API key; the entity is looked up in
  // the caller's own graph, so a foreign/nonexistent id is a 404 upstream.
  const { id } = await params;
  const upstream = await forwardToFastapi(
    `/v1/entities/${encodeURIComponent(id)}/claims`,
  );
  return relayResponse(upstream);
}
