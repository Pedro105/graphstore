"use client";

import { useCallback } from "react";

import { deleteApiKey, listApiKeys } from "@/lib/api";
import { useCachedResource } from "@/lib/hooks/use-cached-resource";

export function useApiKeys() {
  const { data, loading, error, reload } = useCachedResource("api-keys", listApiKeys);

  const remove = useCallback(
    async (id: string) => {
      await deleteApiKey(id);
      await reload();
    },
    [reload],
  );

  return { apiKeys: data ?? [], loading, error, remove, reload };
}
