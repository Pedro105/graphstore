"use client";

import { useCallback, useEffect, useState } from "react";

import { listFrameworks, updateFramework } from "@/lib/api";
import type { Framework } from "@/lib/api";

export function useFrameworks() {
  const [frameworks, setFrameworks] = useState<Framework[]>([]);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    setFrameworks(await listFrameworks());
    setLoading(false);
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const update = useCallback(
    async (id: Framework["id"], patch: Partial<Pick<Framework, "connected" | "config">>) => {
      await updateFramework(id, patch);
      await reload();
    },
    [reload],
  );

  return { frameworks, loading, update };
}
