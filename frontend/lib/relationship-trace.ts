// Turns a recall's flat entities + relations into readable relationship paths
// — chains like "Korrigan Cells Ltd → produces → LFP-9 Cell → named_as_root_
// cause_in → Recall R-2025-014" — rather than an unordered edge list. Pure and
// dependency-free so it can be unit-tested and reused.

import type { Entity, Relation } from "@/lib/api";

export interface TraceStep {
  id: string;
  name: string;
  entityType: string;
  // The relation type linking this step to the next one in the path; undefined
  // on the final step.
  relationToNext?: string;
}

export type TracePath = TraceStep[];

// Guard against pathological cycles producing an unbounded walk.
const MAX_PATH_LENGTH = 24;

interface OutEdge {
  relId: string;
  type: string;
  to: string;
}

/**
 * Stitch relations into linear paths, consuming each edge exactly once.
 *
 * Walks are seeded first from "roots" (entities that are a source but never a
 * target within this result), then from `preferredStartIds` (e.g. the synthesis'
 * grounded entities), then from any remaining node with an unused outgoing edge
 * — so every edge ends up in some path, and cycles still terminate via the
 * used-edge set and the length cap. A path needs at least one hop (two nodes)
 * to be worth showing.
 */
export function buildTraces(
  entities: Entity[],
  relations: Relation[],
  preferredStartIds: string[] = [],
): TracePath[] {
  const entityById = new Map(entities.map((e) => [e.id, e]));
  const out = new Map<string, OutEdge[]>();
  const targets = new Set<string>();

  for (const rel of relations) {
    if (
      !entityById.has(rel.source_entity_id) ||
      !entityById.has(rel.target_entity_id)
    )
      continue;
    const edges = out.get(rel.source_entity_id) ?? [];
    edges.push({
      relId: rel.id,
      type: rel.relation_type,
      to: rel.target_entity_id,
    });
    out.set(rel.source_entity_id, edges);
    targets.add(rel.target_entity_id);
  }

  const used = new Set<string>();
  const paths: TracePath[] = [];

  const roots = entities
    .filter((e) => out.has(e.id) && !targets.has(e.id))
    .map((e) => e.id);
  const preferred = preferredStartIds.filter((id) => out.has(id));
  const everyWithOut = entities.filter((e) => out.has(e.id)).map((e) => e.id);
  // De-duplicated, priority-ordered list of walk seeds.
  const seeds = Array.from(new Set([...roots, ...preferred, ...everyWithOut]));

  for (const seed of seeds) {
    let current = seed;
    const steps: TraceStep[] = [];
    while (steps.length < MAX_PATH_LENGTH) {
      const entity = entityById.get(current);
      if (!entity) break;
      const next = (out.get(current) ?? []).find(
        (edge) => !used.has(edge.relId),
      );
      steps.push({
        id: entity.id,
        name: entity.name,
        entityType: entity.entity_type,
        relationToNext: next?.type,
      });
      if (!next) break;
      used.add(next.relId);
      current = next.to;
    }
    if (steps.length >= 2) paths.push(steps);
  }

  return paths;
}
