// Live feature: the authenticated user's projects (each one its own graph).
// Backed by FastAPI's /v1/projects via this app's /api/projects route handler.
// Listing/creating is user-scoped; switching which project the rest of the
// dashboard acts on is handled by the workspace switcher (lib/dashboard).

import { delJson, getJson, patchJson, postJson } from "@/lib/api/live-client";

export interface Project {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  created_at: string;
}

// POST /v1/projects also returns a freshly minted key, but the dashboard never
// needs it (the switcher uses the existing server-side key + ownership-checked
// X-Project), so it isn't surfaced here.
export interface CreateProjectInput {
  name: string;
  description?: string | null;
}

export async function listProjects(): Promise<Project[]> {
  return getJson<Project[]>("/api/projects");
}

export async function createProject(
  input: CreateProjectInput,
): Promise<Project> {
  return postJson<Project>("/api/projects", input);
}

export async function renameProject(
  tenantId: string,
  name: string,
): Promise<Project> {
  return patchJson<Project>(`/api/projects/${encodeURIComponent(tenantId)}`, {
    name,
  });
}

// Destructive: wipes the project's graph and all its rows. The backend requires
// `confirm` to equal the tenant_id, so the caller must pass it through verbatim.
export async function deleteProject(
  tenantId: string,
  confirm: string,
): Promise<void> {
  return delJson(
    `/api/projects/${encodeURIComponent(tenantId)}?confirm=${encodeURIComponent(confirm)}`,
  );
}
