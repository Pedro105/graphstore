"use client";

import { useCallback, useEffect, useState } from "react";

import { deleteApiKey, listApiKeys } from "@/lib/api";
import type { ApiKey } from "@/lib/api";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

export function useApiKeys() {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setApiKeys(await listApiKeys());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const remove = useCallback(
    async (id: string) => {
      await deleteApiKey(id);
      await reload();
    },
    [reload],
  );

  return { apiKeys, loading, error, remove, reload };
}
