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
