// Live feature: per-entity provenance. Calls this app's /api/entities/[id]/claims
// route handler, which forwards to the tenant-scoped FastAPI endpoint
// GET /v1/entities/{id}/claims. The tenant is derived server-side from the API
// key, so a user only ever sees provenance for their own graph's entities.

import { getJson } from "@/lib/api/live-client";
import type { EntityClaims } from "@/lib/api/types";

export async function fetchEntityClaims(
  entityId: string,
): Promise<EntityClaims> {
  return getJson<EntityClaims>(
    `/api/entities/${encodeURIComponent(entityId)}/claims`,
  );
}
