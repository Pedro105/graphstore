"use client";

import { useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";

import { ActivityFeed } from "@/components/dashboard/activity-feed";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { IngestPanel } from "@/components/memories/ingest-panel";
import { MemoryGraph } from "@/components/memories/memory-graph";
import { ProvenancePanel } from "@/components/memories/provenance-panel";
import { RecallPanel } from "@/components/memories/recall-panel";
import { useActivity } from "@/lib/hooks/use-observability";
import { useAgents } from "@/lib/hooks/use-agents";
import { useMemoryGraph } from "@/lib/hooks/use-memory-graph";
import type { Entity } from "@/lib/api";

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

  const { agents } = useAgents();
  const agentNames = useMemo(() => agents.map((agent) => agent.name), [agents]);
  const { activity, loading: activityLoading } = useActivity();

  // The entity whose provenance panel is open (looked up from the graph click).
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedEntity: Entity | null = useMemo(
    () =>
      selectedId ? (entities.find((e) => e.id === selectedId) ?? null) : null,
    [selectedId, entities],
  );

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

      {/* Graph, full width across the page — the canvas is the focus; the
          Remember/Recall panels sit below it (side by side on wide screens). */}
      <div className="flex flex-col gap-3">
        {graphError ? (
          <div className="flex h-[520px] flex-col items-center justify-center gap-3 rounded-xl border border-destructive/40 bg-destructive/5 text-center">
            <p className="max-w-sm text-sm text-destructive">
              Couldn&apos;t reach the backend: {graphError}
            </p>
            <p className="max-w-sm text-xs text-muted-foreground">
              Make sure FalkorDB and the FastAPI server are running (see README
              run steps).
            </p>
            <Button size="sm" variant="outline" onClick={() => reloadGraph()}>
              Retry
            </Button>
          </div>
        ) : loadingGraph ? (
          <div className="h-[520px] w-full overflow-hidden rounded-xl border border-border bg-card">
            <div className="flex flex-wrap gap-1.5 border-b border-border px-3 py-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-5 w-20 rounded-full" />
              ))}
            </div>
            <div className="grid h-[470px] grid-cols-3 gap-4 p-6">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full rounded-lg" />
              ))}
            </div>
          </div>
        ) : entities.length === 0 ? (
          <div className="flex h-[520px] flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-card text-center">
            <p className="font-medium">No memories yet</p>
            <p className="max-w-sm text-sm text-muted-foreground">
              Use the Remember panel below to write something -- entities and
              relations will appear here as the graph grows.
            </p>
          </div>
        ) : (
          <>
            <MemoryGraph
              entities={entities}
              relations={relations}
              highlightedIds={highlightedIds}
              onSelectEntity={setSelectedId}
            />
            <p className="text-xs text-muted-foreground">
              Tip: click any node to see its full provenance — who asserted each
              property and when.
            </p>
          </>
        )}
      </div>

      {/* Remember + Recall, below the graph: side by side on wide screens,
            stacked when narrow. */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <IngestPanel
          onIngest={ingest}
          ingesting={ingesting}
          error={ingestError}
          agents={agentNames}
        />
        <RecallPanel
          onRecall={runRecall}
          onClear={clearRecall}
          recalling={recalling}
          error={recallError}
          result={recallResult}
        />
      </div>

      {/* Write activity, full-width below the graph — a chronological feed of
          agent writes into this project. Grows with its content; the page (not
          a cramped inner box) scrolls. */}
      <section className="rounded-xl bg-card p-6 ring-1 ring-foreground/10">
        <div className="mb-4">
          <h2 className="font-heading text-base font-semibold tracking-tight">
            Write activity
          </h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Chronological feed of agent writes into this project — who wrote
            what, and what was extracted.
          </p>
        </div>
        <ActivityFeed
          items={activity}
          loading={activityLoading && activity.length === 0}
        />
      </section>

      <ProvenancePanel
        entity={selectedEntity}
        onClose={() => setSelectedId(null)}
      />
    </div>
  );
}
