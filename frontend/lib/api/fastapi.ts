// Server-only helper used by app/api/** route handlers to reach FastAPI.
// Never imported from client components -- the browser only ever talks to
// this Next.js app's own /api/* routes, and the API key below never leaves
// the server (no NEXT_PUBLIC_ prefix).

import { cookies } from "next/headers";
import { NextResponse } from "next/server";

// CONTEXTSTORE_API_URL is the new name; FASTAPI_BASE_URL is still honoured as a
// fallback so existing local setups keep working.
export const CONTEXTSTORE_API_URL =
  process.env.CONTEXTSTORE_API_URL ??
  process.env.FASTAPI_BASE_URL ??
  "http://localhost:8000";

const API_KEY = process.env.CONTEXTSTORE_API_KEY;

// The workspace switcher stores the selected project's tenant_id here. It is
// NOT a secret -- a tenant_id is just an identifier, and the backend re-verifies
// on every request that the key's user actually owns it (returning 403
// otherwise). Sent as the X-Project header so the data routes act on the
// selected project instead of the key's default tenant.
export const ACTIVE_PROJECT_COOKIE = "cs_active_project";

export async function forwardToFastapi(
  path: string,
  init?: RequestInit,
  // Project-scoped data routes (remember/recall/graph/agents/keys) carry the
  // selected project; user-scoped routes (the projects list/create proxy) pass
  // false so a stale cookie can never 403 the very call used to recover from it.
  attachProject = true,
): Promise<Response> {
  // Attach the API key as a Bearer token server-side. The backend derives the
  // user (and the key's default tenant) from it; the X-Project header below
  // selects which of that user's projects to act on, ownership-checked server-side.
  const headers = new Headers(init?.headers);
  if (API_KEY) headers.set("Authorization", `Bearer ${API_KEY}`);
  if (attachProject) {
    const active = (await cookies()).get(ACTIVE_PROJECT_COOKIE)?.value;
    if (active) headers.set("X-Project", active);
  }
  return fetch(`${CONTEXTSTORE_API_URL}${path}`, { ...init, headers });
}

// Forward to FastAPI using a caller-supplied Authorization header rather than
// the server-side API key. Used only by the operator admin proxy: the
// ADMIN_TOKEN is an operator credential entered in the browser per session, so
// it rides the incoming request's Authorization header through to the backend's
// /v1/admin/* endpoints. The backend base URL still never reaches the browser.
export async function forwardAdminToFastapi(
  path: string,
  authorization: string | null,
  init?: RequestInit,
): Promise<Response> {
  const headers = new Headers(init?.headers);
  if (authorization) headers.set("Authorization", authorization);
  return fetch(`${CONTEXTSTORE_API_URL}${path}`, { ...init, headers });
}

// Relay an upstream FastAPI response back to the browser: preserve the status
// and forward Retry-After (so the client can surface rate-limit timing).
// Tolerates empty bodies (e.g. 204 from DELETE) and non-JSON bodies (e.g. a
// framework-level plain-text 500) -- a malformed upstream body must surface as
// its real status, never as a JSON-parse crash in this relay.
export async function relayResponse(upstream: Response): Promise<NextResponse> {
  const headers = new Headers();
  const retryAfter = upstream.headers.get("retry-after");
  if (retryAfter) headers.set("Retry-After", retryAfter);

  if (upstream.status === 204) {
    return new NextResponse(null, { status: 204, headers });
  }

  const text = await upstream.text();
  if (!text) {
    return new NextResponse(null, { status: upstream.status, headers });
  }

  try {
    const data: unknown = JSON.parse(text);
    return NextResponse.json(data, { status: upstream.status, headers });
  } catch {
    // Upstream sent a non-JSON body; pass it through verbatim with its status.
    headers.set(
      "Content-Type",
      upstream.headers.get("content-type") ?? "text/plain",
    );
    return new NextResponse(text, { status: upstream.status, headers });
  }
}
