// Data-access layer: the ONLY place UI code talks to data. Components
// import from here (or from a specific module below), never from `fetch`
// or `localStorage` directly.
//
// Two backing modes, per feature:
//
//   "live"  -- memories.ts, recall.ts, graph.ts. Call this Next.js app's
//              own /api/* route handlers, which forward server-side to
//              FastAPI (FASTAPI_BASE_URL). The fixed demo tenant scope is
//              attached server-side in the route handler, never by the
//              browser. Backed by a real FastAPI + FalkorDB service.
//
//   "local" -- frameworks.ts, focus-areas.ts. No backend exists yet, so these
//              read/write localStorage directly via local-store.ts. Every
//              function is still `async` and returns the same shape a live
//              implementation would, so swapping a feature to "live" later
//              means rewriting the body of its functions to call a route
//              handler -- callers and components do not change. (agents.ts and
//              api-keys.ts have since moved to "live", backed by Postgres.)

export * from "@/lib/api/types";
export * from "@/lib/api/local-types";
export * from "@/lib/api/constants";

export { remember } from "@/lib/api/memories";
export type { RememberInput } from "@/lib/api/memories";

export { recall } from "@/lib/api/recall";
export type { RecallInput } from "@/lib/api/recall";

export { fetchGraph } from "@/lib/api/graph";

export { listAgents, createAgent, deleteAgent } from "@/lib/api/agents";
export type { CreateAgentInput } from "@/lib/api/agents";
export { listFrameworks, updateFramework } from "@/lib/api/frameworks";
export {
  listFocusAreas,
  createFocusArea,
  updateFocusArea,
  deleteFocusArea,
} from "@/lib/api/focus-areas";
export { listApiKeys, deleteApiKey } from "@/lib/api/api-keys";
