import { NextRequest } from "next/server";

import { forwardToFastapi, relayResponse } from "@/lib/api/fastapi";

export async function POST(request: NextRequest) {
  const body = await request.json();

  // No scope/tenant_id -- the backend derives the tenant from the API key.
  const upstream = await forwardToFastapi("/v1/memories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      content: body.content,
      source: body.source,
    }),
  });

  return relayResponse(upstream);
}
