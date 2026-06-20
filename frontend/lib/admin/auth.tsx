"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

// The ADMIN_TOKEN is an operator credential, so it is kept deliberately
// ephemeral: held in React state and mirrored only to sessionStorage, which is
// scoped to the tab and cleared when it closes -- never localStorage. A refresh
// keeps the operator signed in; closing the tab drops the token.

const SESSION_KEY = "contextstore_admin_token";

interface AdminAuth {
  token: string | null;
  setToken: (token: string) => void;
  clear: () => void;
}

const AdminAuthContext = createContext<AdminAuth | null>(null);

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(null);

  // Hydrate from sessionStorage after mount (avoids SSR/client mismatch).
  useEffect(() => {
    const stored = sessionStorage.getItem(SESSION_KEY);
    if (stored) setTokenState(stored);
  }, []);

  const setToken = useCallback((next: string) => {
    sessionStorage.setItem(SESSION_KEY, next);
    setTokenState(next);
  }, []);

  const clear = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY);
    setTokenState(null);
  }, []);

  return (
    <AdminAuthContext.Provider value={{ token, setToken, clear }}>
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
