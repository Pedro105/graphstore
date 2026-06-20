// Live feature: agent registry. Backed by Postgres via this app's
// /api/agents route handlers (which forward to FastAPI's /v1/agents, scoped to
// the authenticated tenant). The registry is the multi-agent write story's
// "source" list. No update endpoint exists -- agents are create/list/delete.

import { delJson, getJson, postJson } from "@/lib/api/live-client";
import type { Agent } from "@/lib/api/local-types";

export interface CreateAgentInput {
  name: string;
  description?: string | null;
}

export async function listAgents(): Promise<Agent[]> {
  return getJson<Agent[]>("/api/agents");
}

export async function createAgent(input: CreateAgentInput): Promise<Agent> {
  return postJson<Agent>("/api/agents", input);
}

export async function deleteAgent(id: string): Promise<void> {
  return delJson(`/api/agents/${id}`);
}
