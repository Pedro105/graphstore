import { forwardToFastapi, relayResponse } from "@/lib/api/fastapi";

// Runs as a Cloudflare Pages edge function (@cloudflare/next-on-pages).
export const runtime = "edge";

export async function GET() {
  // tenant is derived server-side from the API key; no tenant_id query param.
  const upstream = await forwardToFastapi("/v1/graph");
  return relayResponse(upstream);
}
