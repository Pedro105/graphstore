// Wire types mirroring the backend's pydantic models (src/contextstore/models/).
// Field names are kept snake_case to match the JSON the FastAPI service
// actually emits -- no case translation layer.

export type ScopeValue = string | number | boolean;

export type Scope = Record<string, ScopeValue> & { tenant_id: string };

export interface Provenance {
  source: string;
  created_at: string;
  confidence: number;
  evidence: string[] | null;
  supersedes: string[] | null;
}

export interface Entity {
  id: string;
  name: string;
  entity_type: string;
  properties: Record<string, unknown>;
  scope: Scope;
  provenance: Provenance;
  embedding: number[] | null;
  merge_candidates: string[];
}

export interface Relation {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relation_type: string;
  properties: Record<string, unknown>;
  scope: Scope;
  provenance: Provenance;
}

export interface Memory {
  id: string;
  content: string;
  entities: Entity[];
  relations: Relation[];
  scope: Scope;
  provenance: Provenance;
}

// Timing + graph metrics emitted by the backend on every recall (mirrors
// RetrievalStats in src/contextstore/models/recall.py). Always present.
export interface RetrievalStats {
  total_ms: number;
  retrieval_ms: number;
  synthesis_ms: number | null;
  seeds_found: number;
  nodes_traversed: number;
  relations_found: number;
  depth_reached: number;
  query_class: string;
  used_llm_classifier: boolean;
}

export interface RecallResult {
  query: string;
  scope: Scope;
  entities: Entity[];
  relations: Relation[];
  stats: RetrievalStats;
}

export interface GraphSnapshot {
  entities: Entity[];
  relations: Relation[];
}
