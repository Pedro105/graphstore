"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// Stale-while-revalidate cache shared across the dashboard's read hooks. The
// dashboard pages remount on every tab switch (App Router), so without this
// each visit refetches from scratch and flashes a spinner. With it, a revisited
// tab renders its previous data instantly and revalidates quietly in the
// background.
//
// Module-level on purpose: switching projects does a full page reload (see
// lib/dashboard/workspace), which wipes this map -- so cached data never leaks
// across projects.
const cache = new Map<string, unknown>();

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

interface CachedResource<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  mutate: (next: T) => void;
}

export function useCachedResource<T>(key: string, fetcher: () => Promise<T>): CachedResource<T> {
  const cached = cache.has(key) ? (cache.get(key) as T) : null;
  const [data, setData] = useState<T | null>(cached);
  // Only show the spinner on a true cold load (nothing cached yet).
  const [loading, setLoading] = useState(!cache.has(key));
  const [error, setError] = useState<string | null>(null);

  // Keep the latest fetcher without making it an effect dependency (callers
  // pass a fresh closure each render).
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const load = useCallback(
    async (background: boolean) => {
      if (!background) setLoading(true);
      setError(null);
      try {
        const result = await fetcherRef.current();
        cache.set(key, result);
        setData(result);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    },
    [key],
  );

  useEffect(() => {
    // Cached -> revalidate in the background (no spinner); cold -> foreground.
    void load(cache.has(key));
  }, [key, load]);

  const reload = useCallback(() => load(false), [load]);

  const mutate = useCallback(
    (next: T) => {
      cache.set(key, next);
      setData(next);
    },
    [key],
  );

  return { data, loading, error, reload, mutate };
}
