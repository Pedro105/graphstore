import { NextRequest } from "next/server";

import { forwardToFastapi, relayResponse } from "@/lib/api/fastapi";

// These are user-scoped (they list/create the authenticated user's projects),
// so they pass attachProject=false: the active-project cookie is irrelevant
// here, and not sending X-Project keeps the project list reachable even if the
// cookie points at a since-deleted project (otherwise the very call used to
// recover the switcher could 403).

// Runs as a Cloudflare Pages edge function (@cloudflare/next-on-pages).
export const runtime = "edge";

export async function GET() {
  const upstream = await forwardToFastapi("/v1/projects", undefined, false);
  return relayResponse(upstream);
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const upstream = await forwardToFastapi(
    "/v1/projects",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: body.name,
        description: body.description ?? null,
      }),
    },
    false,
  );
  return relayResponse(upstream);
}
