"use client";

import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

import { cn } from "@/lib/utils";

export interface EntityNodeData extends Record<string, unknown> {
  label: string;
  entityType: string;
  highlighted: boolean;
  dimmed: boolean;
}

export type EntityNodeType = Node<EntityNodeData, "entity">;

export function EntityNode({ data }: NodeProps<EntityNodeType>) {
  return (
    <div
      className={cn(
        "animate-in fade-in zoom-in-95 rounded-lg border bg-card px-3 py-2 text-sm shadow-sm duration-300 transition-opacity",
        data.highlighted ? "border-primary ring-2 ring-primary/50" : "border-border",
        data.dimmed && "opacity-25",
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-muted-foreground" />
      <div className="max-w-40 truncate font-medium">{data.label}</div>
      <div className="font-mono text-[10px] text-muted-foreground">{data.entityType}</div>
      <Handle type="source" position={Position.Right} className="!bg-muted-foreground" />
    </div>
  );
}
