import { NextRequest } from "next/server";

import { forwardToFastapi, relayResponse } from "@/lib/api/fastapi";

// Runs as a Cloudflare Pages edge function (@cloudflare/next-on-pages).
export const runtime = "edge";

export async function DELETE(_request: NextRequest, context: { params: Promise<{ id: string }> }) {
  // Tenant-scoped revocation: the backend only revokes a key owned by the
  // caller's tenant (resolved from the API key), else 404.
  const { id } = await context.params;
  const upstream = await forwardToFastapi(`/v1/keys/${id}`, { method: "DELETE" });
  return relayResponse(upstream);
}
