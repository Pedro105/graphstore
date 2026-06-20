// Live feature: API keys. Backed by FastAPI via this app's /api/keys route
// handlers, scoped to the authenticated tenant. Listing returns safe metadata
// only (never the raw key/hash). Creation is operator-only (admin token) and
// not exposed here yet -- the page lists existing keys and revokes them.

import { delJson, getJson } from "@/lib/api/live-client";
import type { ApiKey } from "@/lib/api/local-types";

export async function listApiKeys(): Promise<ApiKey[]> {
  return getJson<ApiKey[]>("/api/keys");
}

export async function deleteApiKey(id: string): Promise<void> {
  return delJson(`/api/keys/${id}`);
}
