"use client";

import { useCallback, useEffect, useState } from "react";

import { useAdminAuth } from "@/lib/admin/auth";
import { AdminApiError } from "@/lib/admin/client";

interface AdminQuery<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

// Run an admin API loader with the current token, tracking loading/error state.
// A 401 means the token went bad -- sign the operator out so the token gate
// takes over rather than leaving stale errors on the page.
export function useAdminQuery<T>(
  loader: (token: string) => Promise<T>,
  deps: readonly unknown[] = [],
): AdminQuery<T> {
  const { token, clear } = useAdminAuth();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    loader(token)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof AdminApiError && err.status === 401) {
          clear();
          return;
        }
        setError(err instanceof Error ? err.message : "Request failed.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, nonce, ...deps]);

  return { data, error, loading, reload };
}
