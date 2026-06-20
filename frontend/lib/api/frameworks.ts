// Local feature: framework connections. Fixed set of integrations
// (LangGraph/CrewAI/AutoGen/MCP) -- "create" doesn't apply, only
// connect/configure state, persisted locally until a real backend exists.

import { readLocal, writeLocal } from "@/lib/api/local-store";
import type { Framework } from "@/lib/api/local-types";

const STORAGE_KEY = "contextstore.frameworks";

const DEFAULT_FRAMEWORKS: Framework[] = [
  {
    id: "langgraph",
    label: "LangGraph",
    description: "Connect a LangGraph app so its nodes can read and write shared memory.",
    connected: false,
    config: {},
    updated_at: null,
  },
  {
    id: "crewai",
    label: "CrewAI",
    description: "Give every agent in a CrewAI crew access to the same memory graph.",
    connected: false,
    config: {},
    updated_at: null,
  },
  {
    id: "autogen",
    label: "AutoGen",
    description: "Wire AutoGen agents to read and write through ContextStore.",
    connected: false,
    config: {},
    updated_at: null,
  },
  {
    id: "mcp",
    label: "MCP",
    description: "Expose remember/recall as MCP tools for Claude Code/Desktop.",
    connected: false,
    config: {},
    updated_at: null,
  },
];

function load(): Framework[] {
  return readLocal<Framework[]>(STORAGE_KEY, DEFAULT_FRAMEWORKS);
}

function save(frameworks: Framework[]): void {
  writeLocal(STORAGE_KEY, frameworks);
}

export async function listFrameworks(): Promise<Framework[]> {
  return load();
}

export async function updateFramework(
  id: Framework["id"],
  patch: Partial<Pick<Framework, "connected" | "config">>,
): Promise<Framework> {
  const frameworks = load();
  const index = frameworks.findIndex((framework) => framework.id === id);
  if (index === -1) throw new Error(`Framework ${id} not found`);
  const updated: Framework = { ...frameworks[index], ...patch, updated_at: new Date().toISOString() };
  frameworks[index] = updated;
  save(frameworks);
  return updated;
}
