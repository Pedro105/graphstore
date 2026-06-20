"use client";

import { useCallback, useEffect, useState } from "react";

import { createFocusArea, deleteFocusArea, listFocusAreas, updateFocusArea } from "@/lib/api";
import type { FocusArea } from "@/lib/api";

export function useFocusAreas() {
  const [focusAreas, setFocusAreas] = useState<FocusArea[]>([]);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    setFocusAreas(await listFocusAreas());
    setLoading(false);
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const create = useCallback(
    async (input: Omit<FocusArea, "id" | "created_at">) => {
      await createFocusArea(input);
      await reload();
    },
    [reload],
  );

  const update = useCallback(
    async (id: string, patch: Partial<Omit<FocusArea, "id">>) => {
      await updateFocusArea(id, patch);
      await reload();
    },
    [reload],
  );

  const remove = useCallback(
    async (id: string) => {
      await deleteFocusArea(id);
      await reload();
    },
    [reload],
  );

  return { focusAreas, loading, create, update, remove };
}
