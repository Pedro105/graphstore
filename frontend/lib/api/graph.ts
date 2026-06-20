// Live feature: full-graph read. Calls this app's /api/graph route handler,
// which forwards to FastAPI's GET /v1/graph -- the one additive backend
// endpoint added for this UI (see api/routes.py for why: there was no
// existing way to read back a tenant's full entity/relation set).

import { getJson } from "@/lib/api/live-client";
import type { GraphSnapshot } from "@/lib/api/types";

export async function fetchGraph(): Promise<GraphSnapshot> {
  return getJson<GraphSnapshot>("/api/graph");
}
