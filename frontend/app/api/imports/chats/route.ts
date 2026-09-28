import { NextRequest } from "next/server";

import { forwardToFastapi, relayResponse } from "@/lib/api/fastapi";

export async function POST(request: NextRequest) {
  const body = await request.json();

  const upstream = await forwardToFastapi("/v1/imports/chats", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      content: body.content,
      source_prefix: body.source_prefix ?? "chat-import",
    }),
  });

  return relayResponse(upstream);
}
