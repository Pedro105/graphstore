import { forwardToFastapi, relayResponse } from "@/lib/api/fastapi";

export async function GET() {
  // tenant is derived server-side from the API key; no tenant_id query param.
  const upstream = await forwardToFastapi("/v1/activity");
  return relayResponse(upstream);
}
