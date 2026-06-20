// Live feature: write path. Calls this app's /api/remember route handler,
// which forwards to FastAPI's POST /v1/memories with the fixed demo tenant
// scope attached server-side.

import { postJson } from "@/lib/api/live-client";
import type { Memory } from "@/lib/api/types";

export interface RememberInput {
  content: string;
  source: string;
}

export async function remember(input: RememberInput): Promise<Memory> {
  return postJson<Memory>("/api/remember", input);
}
