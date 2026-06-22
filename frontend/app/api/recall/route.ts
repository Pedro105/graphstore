import { NextRequest } from "next/server";

import { forwardToFastapi, relayResponse } from "@/lib/api/fastapi";

export async function POST(request: NextRequest) {
  const body = await request.json();

  // No scope/tenant_id -- the backend derives the tenant from the API key.
  // traversal_depth/retrieval_mode are forwarded only when the caller pins
  // them; left unset, the backend's query classifier chooses routing (and the
  // returned stats report the real query_class / depth_reached rather than
  // "manual"). synthesise is forwarded when requested.
  const payload: Record<string, unknown> = {
    query: body.query,
    limit: body.limit ?? 10,
  };
  if (body.traversal_depth !== undefined) payload.traversal_depth = body.traversal_depth;
  if (body.retrieval_mode !== undefined) payload.retrieval_mode = body.retrieval_mode;
  if (body.synthesise !== undefined) payload.synthesise = body.synthesise;

  const upstream = await forwardToFastapi("/v1/recall", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return relayResponse(upstream);
}
