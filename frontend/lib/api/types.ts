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

// How recall() seeds entities before traversal (mirrors RetrievalMode in
// src/contextstore/models/classification.py).
export type RetrievalMode = "vector" | "fulltext" | "hybrid";

// The shape the query classifier routed the recall into.
export type QueryClass = "exact_lookup" | "single_hop" | "relational";

export interface RetrievalStrategy {
  retrieval_mode: RetrievalMode;
  traversal_depth: number;
}

// Why a recall was routed the way it was (mirrors ClassifierResult). Present
// only when the caller left routing unpinned, so the classifier actually ran.
export interface ClassifierResult {
  query_class: QueryClass;
  confidence: number;
  strategy: RetrievalStrategy;
  used_llm: boolean;
}

export type SynthesisConfidence =
  | "high"
  | "medium"
  | "low"
  | "insufficient_data";

// Optional natural-language answer synthesised from the retrieved subgraph
// (mirrors SynthesisResult). Present only when recall was asked to synthesise.
export interface SynthesisResult {
  answer: string;
  grounded_entity_ids: string[];
  confidence: SynthesisConfidence;
  caveat: string | null;
}

export interface RecallResult {
  query: string;
  scope: Scope;
  entities: Entity[];
  relations: Relation[];
  // Present when the classifier ran (routing wasn't pinned); null otherwise.
  classifier_result: ClassifierResult | null;
  // True when multi-hop traversal hit the entity cap and the subgraph was cut.
  truncated: boolean;
  // Present only when recall was called with synthesise=true and it succeeded.
  synthesis: SynthesisResult | null;
  stats: RetrievalStats;
}

export interface GraphSnapshot {
  entities: Entity[];
  relations: Relation[];
}

// --- Observability (mirrors the tenant-scoped /v1/analytics, /v1/activity,
// --- /v1/sources read endpoints in src/contextstore/api/routes.py) -----------

export interface WritePoint {
  day: string;
  count: number;
}

export interface TokenPoint {
  day: string;
  tokens: number;
}

export interface LatencyPoint {
  day: string;
  count: number;
  p50: number | null;
  p95: number | null;
}

export interface ClassCount {
  query_class: string;
  count: number;
}

export interface Analytics {
  writes_over_time: WritePoint[];
  tokens_over_time: TokenPoint[];
  recall_latency: LatencyPoint[];
  query_class_breakdown: ClassCount[];
}

// One recent write into the tenant's graph (mirrors ActivityItem).
export interface ActivityItem {
  id: string;
  source: string;
  raw_content: string;
  extracted_entity_count: number;
  extracted_relation_count: number;
  created_at: string;
}

// Per-agent contribution to the tenant's graph (mirrors SourceActivity).
export interface SourceActivity {
  source: string;
  write_count: number;
  entities: number;
  relations: number;
  last_activity_at: string;
}

// One source's assertion about an entity (mirrors models/claim.py Claim).
// `value` is whatever was asserted for `property_name`; null property_name
// means the source touched the entity without asserting a specific property.
export interface Claim {
  id: string;
  property_name: string | null;
  value: unknown;
  provenance: Provenance;
}

// A claim flagged as superseded by a later one (mirrors AnnotatedClaim).
export interface AnnotatedClaim {
  claim: Claim;
  superseded: boolean;
}

// Full provenance history for one entity (mirrors EntityClaimsResponse from
// the user-facing GET /v1/entities/{id}/claims).
export interface EntityClaims {
  entity_id: string;
  entity_name: string;
  entity_type: string;
  claims: AnnotatedClaim[];
}

// --- Usage monitoring (mirrors the tenant-scoped GET /v1/usage) ---------------

export interface UsageDayPoint {
  date: string;
  recalls: number;
  writes: number;
  tokens: number;
}

export interface EndpointUsage {
  calls: number;
  tokens: number;
}

export interface AgentUsage {
  source: string;
  writes: number;
  last_active: string;
}

export interface Usage {
  period: string;
  total_recalls: number;
  total_writes: number;
  tokens_used: number;
  // Estimated from a placeholder token rate — surfaced as "~" in the UI.
  estimated_cost_usd: number;
  by_day: UsageDayPoint[];
  by_endpoint: Record<string, EndpointUsage>;
  by_agent: AgentUsage[];
}
