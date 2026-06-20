// Wire types for the operator admin API, mirroring the response models in
// src/contextstore/api/admin_routes.py. snake_case to match the JSON the
// backend emits (same convention as lib/api/types.ts).

import type { Entity, GraphSnapshot, Provenance } from "@/lib/api";

export type { Entity, GraphSnapshot };

export interface AdminUser {
  id: string;
  email: string;
  created_at: string;
  project_count: number;
}

export interface AdminProject {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  created_at: string;
  owner_user_id: string;
  owner_email: string;
  last_activity_at: string | null;
  node_count: number;
  edge_count: number;
}

export interface AdminMemoryWrite {
  id: string;
  tenant_id: string;
  source: string;
  raw_content: string;
  extracted_entity_count: number;
  extracted_relation_count: number;
  created_at: string;
}

export interface Claim {
  id: string;
  property_name: string | null;
  value: unknown;
  provenance: Provenance;
}

export interface AnnotatedClaim {
  claim: Claim;
  superseded: boolean;
}

export interface EntityClaims {
  entity_id: string;
  entity_name: string;
  entity_type: string;
  claims: AnnotatedClaim[];
}

export interface AdminUsageRow {
  id: string;
  api_key_id: string;
  tenant_id: string;
  endpoint: string;
  tokens_used: number | null;
  created_at: string;
}

// --- Analytics (admin overview charts) ---

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

export interface TopProject {
  tenant_id: string;
  name: string | null;
  writes: number;
  recalls: number;
  total: number;
}

export interface Analytics {
  writes_over_time: WritePoint[];
  tokens_over_time: TokenPoint[];
  recall_latency: LatencyPoint[];
  query_class_breakdown: ClassCount[];
  top_projects: TopProject[];
}

// --- Per-project sources breakdown ---

export interface ProjectSource {
  source: string;
  write_count: number;
  entities: number;
  relations: number;
  last_activity_at: string;
}

// --- Facts table ---

export interface Fact {
  tenant_id: string;
  entity_id: string;
  entity_name: string;
  entity_type: string;
  property_name: string | null;
  value: unknown;
  source: string;
  asserted_at: string;
  superseded: boolean;
}

export interface FactsResponse {
  facts: Fact[];
  total: number;
  page: number;
  page_size: number;
  truncated: boolean;
}

export interface FactsQuery {
  tenant_id?: string;
  source?: string;
  include_superseded?: boolean;
  q?: string;
  page?: number;
  page_size?: number;
}
