// Live feature: read path. Calls this app's /api/recall route handler,
// which forwards to FastAPI's POST /v1/recall with the fixed demo tenant
// scope attached server-side.

import { postJson } from "@/lib/api/live-client";
import type { RecallResult } from "@/lib/api/types";

export interface RecallInput {
  query: string;
  limit?: number;
  traversal_depth?: number;
}

export async function recall(input: RecallInput): Promise<RecallResult> {
  return postJson<RecallResult>("/api/recall", input);
}
