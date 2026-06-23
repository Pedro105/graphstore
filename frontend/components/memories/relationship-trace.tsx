"use client";

import { useMemo } from "react";
import { ArrowRight } from "lucide-react";

import { buildEntityColorMap, colorForType } from "@/lib/entity-colors";
import { buildTraces } from "@/lib/relationship-trace";
import { cn } from "@/lib/utils";
import type { Entity, Relation } from "@/lib/api";

// Number of paths shown before collapsing the remainder into a count.
const MAX_PATHS = 6;

function EntityChip({
  name,
  color,
  grounded,
}: {
  name: string;
  color: string;
  grounded: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex max-w-[12rem] items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium",
        grounded ? "bg-card" : "bg-card/60",
      )}
      style={{ borderColor: grounded ? color : "var(--border)" }}
      title={name}
    >
      <span
        className="size-1.5 shrink-0 rounded-full"
        style={{ backgroundColor: color }}
      />
      <span className="truncate">{name}</span>
    </span>
  );
}

export function RelationshipTrace({
  entities,
  relations,
  groundedIds,
}: {
  entities: Entity[];
  relations: Relation[];
  groundedIds: string[];
}) {
  const colorMap = useMemo(
    () => buildEntityColorMap(entities.map((e) => e.entity_type)),
    [entities],
  );
  const grounded = useMemo(() => new Set(groundedIds), [groundedIds]);
  const paths = useMemo(
    () => buildTraces(entities, relations, groundedIds),
    [entities, relations, groundedIds],
  );

  if (paths.length === 0) return null;

  const shown = paths.slice(0, MAX_PATHS);
  const hidden = paths.length - shown.length;

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        How we got there
      </p>
      <div className="flex flex-col gap-2.5">
        {shown.map((path, pathIndex) => (
          <div
            key={pathIndex}
            className="flex flex-wrap items-center gap-x-1 gap-y-1.5 rounded-lg border border-border bg-muted/30 p-2.5"
          >
            {path.map((step, stepIndex) => (
              <span
                key={`${step.id}-${stepIndex}`}
                className="inline-flex items-center gap-1"
              >
                <EntityChip
                  name={step.name}
                  color={colorForType(step.entityType, colorMap)}
                  grounded={grounded.has(step.id)}
                />
                {step.relationToNext ? (
                  <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                    <ArrowRight className="size-3" />
                    <span className="font-mono">{step.relationToNext}</span>
                    <ArrowRight className="size-3" />
                  </span>
                ) : null}
              </span>
            ))}
          </div>
        ))}
      </div>
      {hidden > 0 ? (
        <p className="text-xs text-muted-foreground">
          +{hidden} more path{hidden === 1 ? "" : "s"} in the full graph context
          below.
        </p>
      ) : null}
    </div>
  );
}
