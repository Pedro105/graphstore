"use client";

import { useCallback, useMemo, useState } from "react";
import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
} from "@xyflow/react";
import { Sparkles } from "lucide-react";

import {
  EntityNode,
  type EntityNodeType,
} from "@/components/memories/entity-node";
import { buildEntityColorMap, colorForType } from "@/lib/entity-colors";
import { layoutGraph } from "@/lib/graph-layout";
import { cn } from "@/lib/utils";
import type { Entity, Relation } from "@/lib/api";

const nodeTypes = { entity: EntityNode };

// Nodes written within this window are flagged "recent" (pulse) and can be
// isolated via the Recent toggle.
const RECENT_WINDOW_MS = 24 * 60 * 60 * 1000;

interface MemoryGraphProps {
  entities: Entity[];
  relations: Relation[];
  // Entity ids touched by the last recall (null when no recall is active).
  highlightedIds: Set<string> | null;
  // Clicking a node selects it (opens the provenance panel upstream).
  onSelectEntity?: (entityId: string) => void;
}

export function MemoryGraph({
  entities,
  relations,
  highlightedIds,
  onSelectEntity,
}: MemoryGraphProps) {
  // Active type filters (empty = show all) and the "isolate recent" toggle.
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
  const [emphasizeRecent, setEmphasizeRecent] = useState(false);

  const colorMap = useMemo(
    () => buildEntityColorMap(entities.map((e) => e.entity_type)),
    [entities],
  );

  const distinctTypes = useMemo(() => Array.from(colorMap.keys()), [colorMap]);

  const recentIds = useMemo(() => {
    const cutoff = Date.now() - RECENT_WINDOW_MS;
    const ids = new Set<string>();
    for (const entity of entities) {
      const created = entity.provenance?.created_at;
      if (created && new Date(created).getTime() >= cutoff) ids.add(entity.id);
    }
    return ids;
  }, [entities]);

  const { nodes, edges } = useMemo(() => {
    const positions = layoutGraph(
      entities.map((entity) => ({ id: entity.id })),
      relations.map((relation) => ({
        id: relation.id,
        source: relation.source_entity_id,
        target: relation.target_entity_id,
      })),
    );

    const typeActive = selectedTypes.size > 0;
    const recallActive = highlightedIds !== null;

    const isVisible = (entity: Entity): boolean => {
      const inType = !typeActive || selectedTypes.has(entity.entity_type);
      const inRecall = !recallActive || highlightedIds.has(entity.id);
      const inRecent = !emphasizeRecent || recentIds.has(entity.id);
      return inType && inRecall && inRecent;
    };

    const nodes: EntityNodeType[] = entities.map((entity) => ({
      id: entity.id,
      type: "entity",
      position: positions.get(entity.id) ?? { x: 0, y: 0 },
      data: {
        label: entity.name,
        entityType: entity.entity_type,
        color: colorForType(entity.entity_type, colorMap),
        highlighted: recallActive && highlightedIds.has(entity.id),
        dimmed: !isVisible(entity),
        recent: recentIds.has(entity.id),
      },
    }));

    const visibleById = new Map(entities.map((e) => [e.id, isVisible(e)]));

    const edges: Edge[] = relations.map((relation) => {
      const endpointsVisible =
        (visibleById.get(relation.source_entity_id) ?? false) &&
        (visibleById.get(relation.target_entity_id) ?? false);
      const recallRelevant =
        recallActive &&
        highlightedIds.has(relation.source_entity_id) &&
        highlightedIds.has(relation.target_entity_id);
      return {
        id: relation.id,
        source: relation.source_entity_id,
        target: relation.target_entity_id,
        label: relation.relation_type,
        animated: recallRelevant,
        style: endpointsVisible ? undefined : { opacity: 0.12 },
        labelStyle: { fontSize: 10 },
      };
    });

    return { nodes, edges };
  }, [
    entities,
    relations,
    highlightedIds,
    selectedTypes,
    emphasizeRecent,
    recentIds,
    colorMap,
  ]);

  function toggleType(type: string) {
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }

  const recentCount = recentIds.size;

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => onSelectEntity?.(node.id),
    [onSelectEntity],
  );

  return (
    <div className="flex h-[520px] w-full flex-col overflow-hidden rounded-xl border border-border bg-card">
      {/* Legend + filters: click a type to isolate it, click again to clear. */}
      <div className="flex flex-wrap items-center gap-1.5 border-b border-border px-3 py-2">
        {distinctTypes.map((type) => {
          const active = selectedTypes.has(type);
          const color = colorForType(type, colorMap);
          return (
            <button
              key={type}
              type="button"
              onClick={() => toggleType(type)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[11px] transition-colors",
                active
                  ? "border-transparent text-white"
                  : "border-border text-muted-foreground hover:bg-muted",
              )}
              style={active ? { backgroundColor: color } : undefined}
              aria-pressed={active}
            >
              <span
                className="size-1.5 rounded-full"
                style={{ backgroundColor: active ? "white" : color }}
              />
              {type}
            </button>
          );
        })}
        <div className="ml-auto flex items-center gap-1.5">
          {selectedTypes.size > 0 ? (
            <button
              type="button"
              onClick={() => setSelectedTypes(new Set())}
              className="rounded-full px-2 py-0.5 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              Clear
            </button>
          ) : null}
          {recentCount > 0 ? (
            <button
              type="button"
              onClick={() => setEmphasizeRecent((v) => !v)}
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] transition-colors",
                emphasizeRecent
                  ? "border-transparent bg-data-accent text-data-accent-foreground"
                  : "border-border text-muted-foreground hover:bg-muted",
              )}
              aria-pressed={emphasizeRecent}
            >
              <Sparkles className="size-3" />
              Recent 24h · {recentCount}
            </button>
          ) : null}
        </div>
      </div>

      <div className="relative min-h-0 flex-1">
        <ReactFlowProvider>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            onNodeClick={handleNodeClick}
            proOptions={{ hideAttribution: true }}
          >
            <Background />
            <Controls showInteractive={false} />
          </ReactFlow>
        </ReactFlowProvider>
      </div>
    </div>
  );
}
