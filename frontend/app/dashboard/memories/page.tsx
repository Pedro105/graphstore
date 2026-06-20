"use client";

import { useMemo } from "react";
import { Loader2, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { IngestPanel } from "@/components/memories/ingest-panel";
import { MemoryGraph } from "@/components/memories/memory-graph";
import { RecallPanel } from "@/components/memories/recall-panel";
import { useMemoryGraph } from "@/lib/hooks/use-memory-graph";

export default function MemoriesPage() {
  const {
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
    reloadGraph,
  } = useMemoryGraph();

  const highlightedIds = recallResult
    ? new Set(recallResult.entities.map((entity) => entity.id))
    : null;

  // Project-level "last updated" = the most recent provenance timestamp across
  // the graph (distinct from the per-recall stats popover, which is query-level).
  const lastUpdated = useMemo(() => {
    const times = [...entities, ...relations]
      .map((item) => item.provenance?.created_at)
      .filter((t): t is string => Boolean(t));
    return times.length > 0 ? times.reduce((a, b) => (a > b ? a : b)) : null;
  }, [entities, relations]);

  const showStats = !graphError && !loadingGraph;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Memories</h1>
          <p className="text-muted-foreground">
            Write into the shared graph and query it back, live against the
            backend.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => reloadGraph()}
          disabled={loadingGraph}
        >
          <RefreshCw className={loadingGraph ? "animate-spin" : ""} />
          Refresh graph
        </Button>
      </div>

      {showStats ? (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "Entities", value: entities.length.toLocaleString() },
            { label: "Relations", value: relations.length.toLocaleString() },
            {
              label: "Last updated",
              value: lastUpdated ? new Date(lastUpdated).toLocaleString() : "—",
            },
          ].map((stat) => (
            <div
              key={stat.label}
              className="rounded-xl border border-border bg-card p-3"
            >
              <div className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                {stat.label}
              </div>
              <div className="mt-0.5 truncate text-lg font-semibold tabular-nums">
                {stat.value}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_380px]">
        <div className="flex flex-col gap-3">
          {graphError ? (
            <div className="flex h-[520px] flex-col items-center justify-center gap-3 rounded-xl border border-destructive/40 bg-destructive/5 text-center">
              <p className="max-w-sm text-sm text-destructive">
                Couldn&apos;t reach the backend: {graphError}
              </p>
              <p className="max-w-sm text-xs text-muted-foreground">
                Make sure FalkorDB and the FastAPI server are running (see
                README run steps).
              </p>
              <Button size="sm" variant="outline" onClick={() => reloadGraph()}>
                Retry
              </Button>
            </div>
          ) : loadingGraph ? (
            <div className="flex h-[520px] items-center justify-center gap-2 rounded-xl border border-border bg-card text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Loading graph...
            </div>
          ) : entities.length === 0 ? (
            <div className="flex h-[520px] flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-card text-center">
              <p className="font-medium">No memories yet</p>
              <p className="max-w-sm text-sm text-muted-foreground">
                Use the panel on the right to remember something -- entities and
                relations will appear here as the graph grows.
              </p>
            </div>
          ) : (
            <MemoryGraph
              entities={entities}
              relations={relations}
              highlightedIds={highlightedIds}
            />
          )}
        </div>

        <div className="flex flex-col gap-4">
          <IngestPanel
            onIngest={ingest}
            ingesting={ingesting}
            error={ingestError}
          />
          <RecallPanel
            onRecall={runRecall}
            onClear={clearRecall}
            recalling={recalling}
            error={recallError}
            result={recallResult}
          />
        </div>
      </div>
    </div>
  );
}
