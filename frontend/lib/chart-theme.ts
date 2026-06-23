// Shared chart colors for the Overview analytics. Kept as concrete values (not
// CSS vars) so they resolve reliably inside recharts' SVG output regardless of
// theme cascade, and so the same series color can be reused in legends/labels.
//
// Writes lead with the brand's warm amber; recalls take a complementary teal.
// Latency p50/p95 and tokens get their own stable hues.

export const CHART = {
  writes: "#b45309", // warm amber — the brand-aligned primary series
  recalls: "#0e7490", // teal — complementary secondary series
  tokens: "#6d28d9", // violet
  p50: "#0e7490",
  p95: "#b45309",
  grid: "#ececec",
  axis: "#9a9a9a",
} as const;

// Distinct hues for the recall query-class breakdown, aligned with the entity
// palette family so the dashboard feels like one system.
export const QUERY_CLASS_COLORS: Record<string, string> = {
  exact_lookup: "#0e7490",
  single_hop: "#15803d",
  relational: "#b45309",
  manual: "#9a9a9a",
};
