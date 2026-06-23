"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Clock } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchEntityClaims } from "@/lib/api";
import type { AnnotatedClaim, Entity, EntityClaims } from "@/lib/api";
import { colorForType } from "@/lib/entity-colors";
import { relativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function ClaimRow({ annotated }: { annotated: AnnotatedClaim }) {
  const { claim, superseded } = annotated;
  const color = colorForType(claim.provenance.source);
  return (
    <li
      className={cn(
        "flex gap-3 py-2.5 first:pt-0 last:pb-0",
        superseded && "opacity-60",
      )}
    >
      <span
        aria-hidden
        className="mt-1 size-2 shrink-0 rounded-full"
        style={{ backgroundColor: color }}
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          {claim.property_name ? (
            <span className="text-sm">
              <span className="text-muted-foreground">
                {claim.property_name}
              </span>{" "}
              <span className={cn("font-medium", superseded && "line-through")}>
                {renderValue(claim.value)}
              </span>
            </span>
          ) : (
            <span className="text-sm text-muted-foreground">
              touched (no property asserted)
            </span>
          )}
          {superseded ? (
            <Badge variant="outline" className="text-[10px]">
              superseded
            </Badge>
          ) : null}
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
          <span className="font-mono" style={{ color }}>
            {claim.provenance.source}
          </span>
          <span className="inline-flex items-center gap-1">
            <Clock className="size-3" />
            {relativeTime(claim.provenance.created_at)}
          </span>
          {claim.provenance.confidence < 1 ? (
            <span>conf {Math.round(claim.provenance.confidence * 100)}%</span>
          ) : null}
        </div>
        {claim.provenance.evidence && claim.provenance.evidence.length > 0 ? (
          <p className="mt-1 border-l-2 border-border pl-2 text-xs text-muted-foreground/80 italic">
            “{claim.provenance.evidence.join(" · ")}”
          </p>
        ) : null}
      </div>
    </li>
  );
}

export function ProvenancePanel({
  entity,
  onClose,
}: {
  entity: Entity | null;
  onClose: () => void;
}) {
  const [claims, setClaims] = useState<EntityClaims | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const entityId = entity?.id ?? null;

  useEffect(() => {
    if (!entityId) return;
    let cancelled = false;
    setClaims(null);
    setError(null);
    setLoading(true);
    fetchEntityClaims(entityId)
      .then((data) => {
        if (!cancelled) setClaims(data);
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : "Couldn't load provenance.",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [entityId]);

  const properties = entity ? Object.entries(entity.properties) : [];
  const typeColor = entity ? colorForType(entity.entity_type) : "var(--border)";

  return (
    <Dialog
      open={entity !== null}
      onOpenChange={(open) => (!open ? onClose() : undefined)}
    >
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        {entity ? (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <span
                  className="size-2.5 rounded-full"
                  style={{ backgroundColor: typeColor }}
                  aria-hidden
                />
                {entity.name}
              </DialogTitle>
            </DialogHeader>

            <div className="flex flex-col gap-5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary" className="font-mono text-[11px]">
                  {entity.entity_type}
                </Badge>
                {entity.provenance?.source ? (
                  <span className="text-xs text-muted-foreground">
                    last asserted by{" "}
                    <span className="font-mono">
                      {entity.provenance.source}
                    </span>
                  </span>
                ) : null}
              </div>

              {/* Current active property view (latest-claim-wins). */}
              <div>
                <p className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  Properties
                </p>
                {properties.length > 0 ? (
                  <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                    {properties.map(([key, value]) => (
                      <div key={key} className="contents">
                        <dt className="font-mono text-muted-foreground">
                          {key}
                        </dt>
                        <dd className="truncate font-medium">
                          {renderValue(value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No properties recorded.
                  </p>
                )}
              </div>

              {/* Ground-truth provenance: every claim, who asserted it, when, and
                  whether it was later superseded. */}
              <div>
                <p className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  Claim history
                </p>
                {loading ? (
                  <ul className="space-y-3">
                    {Array.from({ length: 3 }).map((_, i) => (
                      <li key={i} className="flex gap-3">
                        <Skeleton className="mt-1 size-2 rounded-full" />
                        <div className="flex-1 space-y-1.5">
                          <Skeleton className="h-3 w-40" />
                          <Skeleton className="h-3 w-28" />
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : error ? (
                  <div className="flex items-center gap-2 text-sm text-destructive">
                    <AlertCircle className="size-4" />
                    {error}
                  </div>
                ) : claims && claims.claims.length > 0 ? (
                  <ul className="divide-y divide-border">
                    {claims.claims.map((annotated) => (
                      <ClaimRow
                        key={annotated.claim.id}
                        annotated={annotated}
                      />
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No claim history recorded for this entity.
                  </p>
                )}
              </div>
            </div>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
