import { NextRequest } from "next/server";

import { forwardToFastapi, relayResponse } from "@/lib/api/fastapi";

// Runs as a Cloudflare Pages edge function (@cloudflare/next-on-pages).
export const runtime = "edge";

export async function GET() {
  const upstream = await forwardToFastapi("/v1/agents");
  return relayResponse(upstream);
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const upstream = await forwardToFastapi("/v1/agents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: body.name,
      description: body.description ?? null,
    }),
  });
  return relayResponse(upstream);
}
