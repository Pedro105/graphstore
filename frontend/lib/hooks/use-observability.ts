"use client";

import {
  fetchActivity,
  fetchAnalytics,
  fetchSources,
  fetchUsage,
} from "@/lib/api";
import type { Analytics, ActivityItem, SourceActivity, Usage } from "@/lib/api";
import { useCachedResource } from "@/lib/hooks/use-cached-resource";

// Tenant-scoped observability reads, each stale-while-revalidate cached so tab
// switches are instant (same pattern as use-agents / use-memory-graph). The
// cache keys are project-local: switching projects reloads the page, wiping the
// module-level cache, so one tenant's analytics never leak into another's view.

export function useAnalytics() {
  const { data, loading, error, reload } = useCachedResource<Analytics>(
    "analytics",
    fetchAnalytics,
  );
  return { analytics: data, loading, error, reload };
}

export function useActivity() {
  const { data, loading, error, reload } = useCachedResource<ActivityItem[]>(
    "activity",
    fetchActivity,
  );
  return { activity: data ?? [], loading, error, reload };
}

export function useSources() {
  const { data, loading, error, reload } = useCachedResource<SourceActivity[]>(
    "sources",
    fetchSources,
  );
  return { sources: data ?? [], loading, error, reload };
}

export function useUsage() {
  const { data, loading, error, reload } = useCachedResource<Usage>(
    "usage",
    fetchUsage,
  );
  return { usage: data, loading, error, reload };
}
