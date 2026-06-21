// Thin fetch wrapper shared by the "live" feature modules (memories.ts,
// recall.ts, graph.ts, agents.ts, api-keys.ts). All requests go to this
// Next.js app's own route handlers (app/api/**), which forward server-side to
// FastAPI -- the browser never calls the backend (or sees the API key) directly.

export class ApiError extends Error {
  status?: number;
  // Seconds to wait before retrying, parsed from a 429's Retry-After header.
  retryAfter?: number;

  constructor(message: string, status?: number, retryAfter?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

async function readErrorDetail(res: Response): Promise<string | null> {
  try {
    const data: unknown = await res.json();
    if (typeof data === "object" && data !== null && "detail" in data) {
      const detail = (data as { detail: unknown }).detail;
      return typeof detail === "string" ? detail : JSON.stringify(detail);
    }
    return null;
  } catch {
    return null;
  }
}

// Map an upstream status to a message a user can act on. 401/429 get specific
// copy; everything else falls back to the backend's detail.
function messageForStatus(status: number, detail: string | null, retryAfter?: number): string {
  if (status === 401) return "API key invalid or expired.";
  if (status === 429) {
    return retryAfter
      ? `Too many requests. Try again in ${retryAfter} second${retryAfter === 1 ? "" : "s"}.`
      : "Too many requests. Try again shortly.";
  }
  return detail ?? `Request failed (${status}).`;
}

// Wrap fetch so a network/connection failure (backend down) becomes a typed,
// user-facing ApiError instead of an opaque TypeError.
async function safeFetch(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(path, init);
  } catch {
    throw new ApiError("Backend unavailable. Check the service is running and retry.");
  }
}

async function throwForStatus(res: Response, path: string): Promise<never> {
  const detail = await readErrorDetail(res);
  const header = res.headers.get("retry-after");
  const retryAfter = header ? Number(header) : undefined;
  throw new ApiError(
    messageForStatus(res.status, detail ?? `Request to ${path} failed`, retryAfter),
    res.status,
    Number.isFinite(retryAfter) ? retryAfter : undefined,
  );
}

export async function getJson<T>(path: string): Promise<T> {
  const res = await safeFetch(path);
  if (!res.ok) await throwForStatus(res, path);
  return res.json() as Promise<T>;
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await safeFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) await throwForStatus(res, path);
  return res.json() as Promise<T>;
}

export async function patchJson<T>(path: string, body: unknown): Promise<T> {
  const res = await safeFetch(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) await throwForStatus(res, path);
  return res.json() as Promise<T>;
}

export async function delJson(path: string): Promise<void> {
  const res = await safeFetch(path, { method: "DELETE" });
  if (!res.ok) await throwForStatus(res, path);
  // 204 No Content -- nothing to parse.
}
