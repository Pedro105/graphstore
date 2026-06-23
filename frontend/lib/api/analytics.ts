// Live feature: observability reads. Each calls this app's own route handler
// (app/api/analytics|activity|sources), which forwards to the tenant-scoped
// FastAPI endpoints (/v1/analytics, /v1/activity, /v1/sources). The tenant is
// derived server-side from the API key -- the browser never sends a tenant_id.

import { getJson } from "@/lib/api/live-client";
import type {
  Analytics,
  ActivityItem,
  SourceActivity,
  Usage,
} from "@/lib/api/types";

export async function fetchAnalytics(): Promise<Analytics> {
  return getJson<Analytics>("/api/analytics");
}

export async function fetchActivity(): Promise<ActivityItem[]> {
  return getJson<ActivityItem[]>("/api/activity");
}

export async function fetchSources(): Promise<SourceActivity[]> {
  return getJson<SourceActivity[]>("/api/sources");
}

export async function fetchUsage(): Promise<Usage> {
  return getJson<Usage>("/api/usage");
}
