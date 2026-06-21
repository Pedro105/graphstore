"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import {
  createProject,
  deleteProject as apiDeleteProject,
  listProjects,
  renameProject as apiRenameProject,
  type Project,
} from "@/lib/api";

// Must match ACTIVE_PROJECT_COOKIE in lib/api/fastapi.ts (read server-side by
// the proxy). A tenant_id, not a secret -- the backend re-checks ownership on
// every request, so this only selects *which of your own projects* to act on.
const ACTIVE_PROJECT_COOKIE = "cs_active_project";

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

function writeCookie(name: string, value: string): void {
  // Session-scoped, path=/ so every /api/* route handler sees it. SameSite=Lax
  // is fine -- it rides same-origin navigations to this app's own routes.
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; SameSite=Lax`;
}

interface Workspace {
  projects: Project[];
  activeProject: Project | null;
  loading: boolean;
  switchTo: (tenantId: string) => void;
  createAndSwitch: (name: string) => Promise<void>;
  renameProject: (tenantId: string, name: string) => Promise<void>;
  deleteProject: (tenantId: string, confirm: string) => Promise<void>;
}

const WorkspaceContext = createContext<Workspace | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeTenant, setActiveTenant] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    listProjects()
      .then((ps) => {
        if (cancelled) return;
        setProjects(ps);
        const cookie = readCookie(ACTIVE_PROJECT_COOKIE);
        const valid = cookie && ps.some((p) => p.tenant_id === cookie);
        if (valid) {
          setActiveTenant(cookie);
        } else if (ps.length > 0) {
          // First visit (or stale cookie): pin the active project explicitly and
          // reload once so the rest of the dashboard fetches under it -- keeps
          // the data shown consistent with the switcher's selection.
          writeCookie(ACTIVE_PROJECT_COOKIE, ps[0].tenant_id);
          window.location.reload();
          return;
        }
      })
      .catch(() => {
        /* leave loading -> the dashboard's own error states handle backend down */
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const switchTo = useCallback(
    (tenantId: string) => {
      if (tenantId === activeTenant) return;
      writeCookie(ACTIVE_PROJECT_COOKIE, tenantId);
      // Full reload so every page + data hook refetches against the new project.
      window.location.reload();
    },
    [activeTenant],
  );

  const createAndSwitch = useCallback(async (name: string) => {
    const project = await createProject({ name });
    writeCookie(ACTIVE_PROJECT_COOKIE, project.tenant_id);
    window.location.reload();
  }, []);

  const renameProject = useCallback(async (tenantId: string, name: string) => {
    const updated = await apiRenameProject(tenantId, name);
    // Update in place -- no reload needed; the switcher and any open page read
    // the new name from this state immediately.
    setProjects((ps) =>
      ps.map((p) => (p.tenant_id === tenantId ? updated : p)),
    );
  }, []);

  const deleteProject = useCallback(
    async (tenantId: string, confirm: string) => {
      await apiDeleteProject(tenantId, confirm);
      // If the active project was the one deleted, drop the cookie so the
      // provider re-pins a surviving project on the next load.
      if (readCookie(ACTIVE_PROJECT_COOKIE) === tenantId) {
        document.cookie = `${ACTIVE_PROJECT_COOKIE}=; path=/; SameSite=Lax; max-age=0`;
      }
      // Full navigation so every page + data hook refetches without the project.
      window.location.assign("/dashboard");
    },
    [],
  );

  const activeProject =
    projects.find((p) => p.tenant_id === activeTenant) ?? null;

  return (
    <WorkspaceContext.Provider
      value={{
        projects,
        activeProject,
        loading,
        switchTo,
        createAndSwitch,
        renameProject,
        deleteProject,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): Workspace {
  const ctx = useContext(WorkspaceContext);
  if (ctx === null)
    throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
}
