import { NextRequest } from "next/server";

import { forwardToFastapi, relayResponse } from "@/lib/api/fastapi";

export async function DELETE(_request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const upstream = await forwardToFastapi(`/v1/agents/${id}`, { method: "DELETE" });
  return relayResponse(upstream);
}
