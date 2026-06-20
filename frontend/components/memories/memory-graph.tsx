"use client";

import { useMemo } from "react";
import { Background, Controls, ReactFlow, ReactFlowProvider, type Edge } from "@xyflow/react";

import { EntityNode, type EntityNodeType } from "@/components/memories/entity-node";
import { layoutGraph } from "@/lib/graph-layout";
import type { Entity, Relation } from "@/lib/api";

const nodeTypes = { entity: EntityNode };

interface MemoryGraphProps {
  entities: Entity[];
  relations: Relation[];
  highlightedIds: Set<string> | null;
}

export function MemoryGraph({ entities, relations, highlightedIds }: MemoryGraphProps) {
  const { nodes, edges } = useMemo(() => {
    const positions = layoutGraph(
      entities.map((entity) => ({ id: entity.id })),
      relations.map((relation) => ({
        id: relation.id,
        source: relation.source_entity_id,
        target: relation.target_entity_id,
      })),
    );

    const nodes: EntityNodeType[] = entities.map((entity) => {
      const isHighlighted = highlightedIds?.has(entity.id) ?? false;
      return {
        id: entity.id,
        type: "entity",
        position: positions.get(entity.id) ?? { x: 0, y: 0 },
        data: {
          label: entity.name,
          entityType: entity.entity_type,
          highlighted: highlightedIds !== null && isHighlighted,
          dimmed: highlightedIds !== null && !isHighlighted,
        },
      };
    });

    const edges: Edge[] = relations.map((relation) => {
      const relevant =
        (highlightedIds?.has(relation.source_entity_id) ?? false) &&
        (highlightedIds?.has(relation.target_entity_id) ?? false);
      const dimmed = highlightedIds !== null && !relevant;
      return {
        id: relation.id,
        source: relation.source_entity_id,
        target: relation.target_entity_id,
        label: relation.relation_type,
        animated: highlightedIds !== null && relevant,
        style: dimmed ? { opacity: 0.2 } : undefined,
        labelStyle: { fontSize: 10 },
      };
    });

    return { nodes, edges };
  }, [entities, relations, highlightedIds]);

  return (
    <div className="h-[520px] w-full overflow-hidden rounded-xl border border-border bg-card">
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
