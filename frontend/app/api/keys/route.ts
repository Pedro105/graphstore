import { forwardToFastapi, relayResponse } from "@/lib/api/fastapi";

export async function GET() {
  // Lists the authenticated tenant's own keys (safe metadata only -- the
  // backend never returns the hash or the raw key).
  const upstream = await forwardToFastapi("/v1/keys");
  return relayResponse(upstream);
}
