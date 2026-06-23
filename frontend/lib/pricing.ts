// Cost ESTIMATION only. Mirrors the backend constant _HAIKU_USD_PER_MTOK in
// src/contextstore/api/routes.py — a placeholder Claude Haiku input rate
// ($0.80 / million tokens). usage_log records total tokens (not split
// input/output), so any figure derived here is an estimate and is always
// labelled as such in the UI. Update both constants together when real pricing
// is wired.
export const HAIKU_USD_PER_MTOK = 0.8;

export function estimatedCost(tokens: number): number {
  return (tokens / 1_000_000) * HAIKU_USD_PER_MTOK;
}

// Format a USD cost estimate. Small values keep more precision so a few cents
// don't round to $0.00.
export function formatCost(usd: number): string {
  if (usd === 0) return "$0.00";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}
