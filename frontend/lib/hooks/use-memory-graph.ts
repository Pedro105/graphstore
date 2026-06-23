"use client";

import { useCallback, useState } from "react";

import { fetchGraph, recall, remember } from "@/lib/api";
import type { GraphSnapshot, RecallResult } from "@/lib/api";
import { useCachedResource } from "@/lib/hooks/use-cached-resource";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

export function useMemoryGraph() {
  // The graph snapshot is cached under "graph" -- shared with the dashboard
  // Overview, and instant on tab revisits (revalidated in the background).
  const {
    data: snapshot,
    loading: loadingGraph,
    error: graphError,
    reload: reloadGraph,
  } = useCachedResource<GraphSnapshot>("graph", fetchGraph);

  const [ingesting, setIngesting] = useState(false);
  const [ingestError, setIngestError] = useState<string | null>(null);

  const [recalling, setRecalling] = useState(false);
  const [recallError, setRecallError] = useState<string | null>(null);
  const [recallResult, setRecallResult] = useState<RecallResult | null>(null);

  const ingest = useCallback(
    async (content: string, source: string) => {
      setIngesting(true);
      setIngestError(null);
      try {
        await remember({ content, source });
        await reloadGraph();
      } catch (error) {
        setIngestError(errorMessage(error));
      } finally {
        setIngesting(false);
      }
    },
    [reloadGraph],
  );

  const runRecall = useCallback(async (query: string, synthesise = false) => {
    setRecalling(true);
    setRecallError(null);
    try {
      const result = await recall({ query, synthesise });
      setRecallResult(result);
    } catch (error) {
      setRecallError(errorMessage(error));
      setRecallResult(null);
    } finally {
      setRecalling(false);
    }
  }, []);

  const clearRecall = useCallback(() => {
    setRecallResult(null);
    setRecallError(null);
  }, []);

  return {
    entities: snapshot?.entities ?? [],
    relations: snapshot?.relations ?? [],
    loadingGraph,
    graphError,
    ingesting,
    ingestError,
    ingest,
    recalling,
    recallError,
    recallResult,
    runRecall,
    clearRecall,
    reloadGraph,
  };
}
