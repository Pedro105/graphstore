"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { adminApi, AdminApiError } from "@/lib/admin/client";

// The ADMIN_TOKEN is an operator credential, so it is kept deliberately
// ephemeral: held in React state and mirrored only to sessionStorage, which is
// scoped to the tab and cleared when it closes -- never localStorage. A refresh
// keeps the operator signed in; closing the tab drops the token.
//
// A token is only ever exposed (status "ok") AFTER it has been validated against
// the backend (GET /v1/admin/auth). This makes the auth check a hard gate: no
// data page mounts or fetches until the backend has confirmed the token, so an
// unvalidated/wrong token never triggers data requests.

const SESSION_KEY = "contextstore_admin_token";

type Status = "anon" | "validating" | "ok";

interface AdminAuth {
  token: string | null; // non-null only once validated (status === "ok")
  status: Status;
  error: string | null;
  submit: (token: string) => void;
  clear: () => void;
}

const AdminAuthContext = createContext<AdminAuth | null>(null);

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("anon");
  const [error, setError] = useState<string | null>(null);

  const validate = useCallback(async (candidate: string, silent: boolean) => {
    setStatus("validating");
    setError(null);
    try {
      await adminApi.validate(candidate);
      sessionStorage.setItem(SESSION_KEY, candidate);
      setToken(candidate);
      setStatus("ok");
    } catch (err) {
      sessionStorage.removeItem(SESSION_KEY);
      setToken(null);
      setStatus("anon");
      // On silent (re)hydration of a stored token, don't shout an error -- just
      // fall back to the entry form. On an explicit submit, surface why.
      if (!silent) {
        setError(
          err instanceof AdminApiError
            ? err.message
            : "Could not validate admin token.",
        );
      }
    }
  }, []);

  // Re-validate a token persisted from earlier in the session (e.g. a refresh).
  useEffect(() => {
    const stored = sessionStorage.getItem(SESSION_KEY);
    if (stored) void validate(stored, true);
  }, [validate]);

  const submit = useCallback(
    (next: string) => void validate(next, false),
    [validate],
  );

  const clear = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY);
    setToken(null);
    setStatus("anon");
    setError(null);
  }, []);

  return (
    <AdminAuthContext.Provider value={{ token, status, error, submit, clear }}>
      {children}
    </AdminAuthContext.Provider>
  );
}

export function useAdminAuth(): AdminAuth {
  const ctx = useContext(AdminAuthContext);
  if (ctx === null)
    throw new Error("useAdminAuth must be used within AdminAuthProvider");
  return ctx;
}
