"use client";

import { useCallback, useEffect, useState } from "react";

import { createAgent, deleteAgent, listAgents } from "@/lib/api";
import type { Agent, CreateAgentInput } from "@/lib/api";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

export function useAgents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setAgents(await listAgents());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

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

  return { agents, loading, error, create, remove, reload };
}
