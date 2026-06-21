"use client";

import { useCallback } from "react";

import { createAgent, deleteAgent, listAgents } from "@/lib/api";
import type { CreateAgentInput } from "@/lib/api";
import { useCachedResource } from "@/lib/hooks/use-cached-resource";

export function useAgents() {
  const { data, loading, error, reload } = useCachedResource("agents", listAgents);

  const create = useCallback(
    async (input: CreateAgentInput) => {
      await createAgent(input);
      await reload();
    },
    [reload],
  );

  const remove = useCallback(
    async (id: string) => {
      await deleteAgent(id);
      await reload();
    },
    [reload],
  );

  return { agents: data ?? [], loading, error, create, remove, reload };
}
