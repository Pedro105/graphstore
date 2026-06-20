// Types for the "local" feature modules -- features with no backend yet
// (agents, frameworks, focus areas, API keys). These are not backend
// models; they exist only client-side until a real service backs them.

// Agent is now backend-backed (Postgres, per-tenant) -- shape mirrors the
// FastAPI AgentResponse. `role`/`color` from the old localStorage stub are
// gone; the backend stores name + description.
export interface Agent {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export type FrameworkKey = "langgraph" | "crewai" | "autogen" | "mcp";

export interface Framework {
  id: FrameworkKey;
  label: string;
  description: string;
  connected: boolean;
  config: Record<string, string>;
  updated_at: string | null;
}

export interface FocusArea {
  id: string;
  name: string;
  description: string;
  created_at: string;
}

// ApiKey is now backend-backed -- safe metadata only (the raw key/hash is
// never returned by the API). Mirrors the FastAPI ApiKeyResponse.
export interface ApiKey {
  id: string;
  name: string | null;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}
