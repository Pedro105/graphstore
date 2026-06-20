"use client";

import { useCallback, useEffect, useState } from "react";

import { fetchGraph, recall, remember } from "@/lib/api";
import type { Entity, Relation, RecallResult } from "@/lib/api";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

export function useMemoryGraph() {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [relations, setRelations] = useState<Relation[]>([]);
  const [loadingGraph, setLoadingGraph] = useState(true);
  const [graphError, setGraphError] = useState<string | null>(null);

  const [ingesting, setIngesting] = useState(false);
  const [ingestError, setIngestError] = useState<string | null>(null);

  const [recalling, setRecalling] = useState(false);
  const [recallError, setRecallError] = useState<string | null>(null);
  const [recallResult, setRecallResult] = useState<RecallResult | null>(null);

  const loadGraph = useCallback(async () => {
    setLoadingGraph(true);
    setGraphError(null);
    try {
      const snapshot = await fetchGraph();
      setEntities(snapshot.entities);
      setRelations(snapshot.relations);
    } catch (error) {
      setGraphError(errorMessage(error));
    } finally {
      setLoadingGraph(false);
    }
  }, []);

  useEffect(() => {
    void loadGraph();
  }, [loadGraph]);

  const ingest = useCallback(
    async (content: string, source: string) => {
      setIngesting(true);
      setIngestError(null);
      try {
        await remember({ content, source });
        await loadGraph();
      } catch (error) {
        setIngestError(errorMessage(error));
      } finally {
        setIngesting(false);
      }
    },
    [loadGraph],
  );

  const runRecall = useCallback(async (query: string) => {
    setRecalling(true);
    setRecallError(null);
    try {
      const result = await recall({ query });
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
    entities,
    relations,
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
    reloadGraph: loadGraph,
  };
}
