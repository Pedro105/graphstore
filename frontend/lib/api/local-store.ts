// Shared helper for the "local" feature modules (agents.ts, frameworks.ts,
// focus-areas.ts, api-keys.ts). Backs them with localStorage so dashboard
// sections that have no backend yet still persist across reloads, isolated
// behind the same async function shape the "live" modules use.

const isBrowser = typeof window !== "undefined";

export function readLocal<T>(key: string, fallback: T): T {
  if (!isBrowser) return fallback;
  const raw = window.localStorage.getItem(key);
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeLocal<T>(key: string, value: T): void {
  if (!isBrowser) return;
  window.localStorage.setItem(key, JSON.stringify(value));
}

export function generateId(prefix: string): string {
  const random = isBrowser && "randomUUID" in crypto ? crypto.randomUUID() : Math.random().toString(36).slice(2);
  return `${prefix}_${random}`;
}
