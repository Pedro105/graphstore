import { NextRequest } from "next/server";

import { forwardToFastapi, relayResponse } from "@/lib/api/fastapi";

// Rename / delete a specific project by tenant_id. Like the projects
// list/create routes these are user-scoped and target the project named in the
// path (ownership is re-checked server-side from the key's user), so they pass
// attachProject=false -- the active-project cookie is irrelevant here.

// Runs as a Cloudflare Pages edge function (@cloudflare/next-on-pages).
export const runtime = "edge";

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ tenant_id: string }> },
) {
  const { tenant_id } = await params;
  const body = await request.json();
  const upstream = await forwardToFastapi(
    `/v1/projects/${encodeURIComponent(tenant_id)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: body.name }),
    },
    false,
  );
  return relayResponse(upstream);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ tenant_id: string }> },
) {
  const { tenant_id } = await params;
  // The backend requires ?confirm=<tenant_id> as a deliberate, typed guard.
  const confirm = new URL(request.url).searchParams.get("confirm") ?? "";
  const upstream = await forwardToFastapi(
    `/v1/projects/${encodeURIComponent(tenant_id)}?confirm=${encodeURIComponent(confirm)}`,
    { method: "DELETE" },
    false,
  );
  return relayResponse(upstream);
}
