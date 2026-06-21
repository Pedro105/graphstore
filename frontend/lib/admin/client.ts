// Browser-side client for the operator admin API. Every call goes to this
// Next.js app's own /api/admin/* proxy with the operator's ADMIN_TOKEN as a
// Bearer header; the proxy forwards it to FastAPI /v1/admin/*. The token is
// passed in per call (held in admin auth context, never localStorage).

import type {
  AdminMemoryWrite,
  AdminProject,
  AdminUsageRow,
  AdminUser,
  Analytics,
  EntityClaims,
  FactsQuery,
  FactsResponse,
  GraphSnapshot,
  ProjectSource,
} from "@/lib/admin/types";

export class AdminApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "AdminApiError";
    this.status = status;
  }
}

async function readDetail(res: Response): Promise<string | null> {
  try {
    const data: unknown = await res.json();
    if (typeof data === "object" && data !== null && "detail" in data) {
      const detail = (data as { detail: unknown }).detail;
      return typeof detail === "string" ? detail : JSON.stringify(detail);
    }
  } catch {
    /* non-JSON body */
  }
  return null;
}

async function adminFetch<T>(
  path: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api/admin${path}`, {
      ...init,
      headers: { ...init?.headers, Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new AdminApiError(
      "Backend unavailable. Check the service is running.",
    );
  }
  if (!res.ok) {
    const detail = await readDetail(res);
    const message =
      res.status === 401
        ? "Admin token invalid."
        : (detail ?? `Request failed (${res.status}).`);
    throw new AdminApiError(message, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const adminApi = {
  // Lightweight token check (GET /v1/admin/auth) the gate runs before mounting
  // any data page. Resolves on a valid token; throws (401 invalid / 429 locked
  // out) otherwise.
  validate: (token: string) => adminFetch<{ ok: boolean }>("/auth", token),
  listUsers: (token: string) => adminFetch<AdminUser[]>("/users", token),
  listProjects: (token: string) =>
    adminFetch<AdminProject[]>("/projects", token),
  projectMemories: (token: string, tenantId: string) =>
    adminFetch<AdminMemoryWrite[]>(`/projects/${tenantId}/memories`, token),
  projectGraph: (token: string, tenantId: string) =>
    adminFetch<GraphSnapshot>(`/projects/${tenantId}/graph`, token),
  entityClaims: (token: string, tenantId: string, entityId: string) =>
    adminFetch<EntityClaims>(
      `/projects/${tenantId}/entities/${entityId}/claims`,
      token,
    ),
  usage: (token: string, tenantId?: string) =>
    adminFetch<AdminUsageRow[]>(
      `/usage${tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : ""}`,
      token,
    ),
  analytics: (token: string, days = 30) =>
    adminFetch<Analytics>(`/analytics?days=${days}`, token),
  projectSources: (token: string, tenantId: string) =>
    adminFetch<ProjectSource[]>(`/projects/${tenantId}/sources`, token),
  facts: (token: string, query: FactsQuery = {}) => {
    const params = new URLSearchParams();
    if (query.tenant_id) params.set("tenant_id", query.tenant_id);
    if (query.source) params.set("source", query.source);
    if (query.include_superseded) params.set("include_superseded", "true");
    if (query.q) params.set("q", query.q);
    if (query.page) params.set("page", String(query.page));
    if (query.page_size) params.set("page_size", String(query.page_size));
    const qs = params.toString();
    return adminFetch<FactsResponse>(`/facts${qs ? `?${qs}` : ""}`, token);
  },
  deleteMemoryWrite: (token: string, tenantId: string, memoryWriteId: string) =>
    adminFetch<void>(`/projects/${tenantId}/memories/${memoryWriteId}`, token, {
      method: "DELETE",
    }),
  wipeProject: (token: string, tenantId: string) =>
    adminFetch<{ tenant_id: string; status: string }>(
      `/projects/${tenantId}?confirm=${encodeURIComponent(tenantId)}`,
      token,
      { method: "DELETE" },
    ),
  revokeKey: (token: string, keyId: string) =>
    adminFetch<void>(`/api-keys/${keyId}`, token, { method: "DELETE" }),
};
