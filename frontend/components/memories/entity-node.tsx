"use client";

import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

import { cn } from "@/lib/utils";

export interface EntityNodeData extends Record<string, unknown> {
  label: string;
  entityType: string;
  // Color assigned to this entity's type (see lib/entity-colors).
  color: string;
  // In the last-recall result (drawn emphasised).
  highlighted: boolean;
  // Out of the current focus (recall result or active type filter) — drawn faint.
  dimmed: boolean;
  // Written within the recent window — drawn with an accent pulse.
  recent: boolean;
}

export type EntityNodeType = Node<EntityNodeData, "entity">;

export function EntityNode({ data }: NodeProps<EntityNodeType>) {
  return (
    <div
      className={cn(
        "animate-in fade-in zoom-in-95 relative cursor-pointer rounded-lg border bg-card py-2 pr-3 pl-3.5 text-sm shadow-sm duration-300 transition-opacity hover:shadow-md",
        data.highlighted ? "ring-2 ring-data-accent" : "border-border",
        data.dimmed && "opacity-25",
      )}
      style={{ borderLeftColor: data.color, borderLeftWidth: 3 }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-muted-foreground"
      />
      <div className="max-w-40 truncate font-medium">{data.label}</div>
      <div
        className="flex items-center gap-1.5 font-mono text-[10px]"
        style={{ color: data.color }}
      >
        <span
          className="size-1.5 rounded-full"
          style={{ backgroundColor: data.color }}
        />
        {data.entityType}
      </div>
      {data.recent ? (
        <span
          aria-label="Recently written"
          className="absolute -top-1 -right-1 flex size-2.5"
        >
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-data-accent opacity-60" />
          <span className="relative inline-flex size-2.5 rounded-full bg-data-accent" />
        </span>
      ) : null}
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-muted-foreground"
      />
    </div>
  );
}
