// Small presentational formatting helpers shared across dashboard views.

// "just now" / "5m ago" / "3h ago" / "2d ago", falling back to a date for
// anything older than ~a week. Tolerant of bad input (returns "—").
export function relativeTime(value: string | null | undefined): string {
  if (!value) return "—";
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return "—";
  const seconds = Math.round((Date.now() - then) / 1000);
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

// Compact integer formatting: 1234 -> "1.2k", 2_000_000 -> "2M".
export function compactNumber(value: number): string {
  if (Math.abs(value) < 1000) return String(value);
  return new Intl.NumberFormat(undefined, {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}
