// Deterministic color-per-entity-type, shared by the graph nodes (inline SVG/
// border colors), the graph legend, and anywhere else a type needs a stable
// visual identity. Kept dependency-free so both the client graph component and
// plain UI can import it.
//
// The palette is a harmonious categorical set that reads on a white card. Types
// are assigned colors by first appearance (sorted, for stability across
// renders) rather than by hashing, so a small graph gets maximally distinct
// colors instead of hash collisions.

export const ENTITY_TYPE_PALETTE = [
  "#b45309", // amber-700 (brand-aligned warm accent leads)
  "#0e7490", // cyan-700
  "#6d28d9", // violet-700
  "#15803d", // green-700
  "#be185d", // pink-700
  "#1d4ed8", // blue-700
  "#a16207", // yellow-700
  "#b91c1c", // red-700
  "#0f766e", // teal-700
  "#7c2d12", // orange-900
] as const;

// Fallback for a type not present in a built map (e.g. a node that appeared
// after the map was computed). Stable per string via a small FNV-ish hash.
function hashColor(type: string): string {
  let hash = 0;
  for (let i = 0; i < type.length; i++) {
    hash = (hash * 31 + type.charCodeAt(i)) >>> 0;
  }
  return ENTITY_TYPE_PALETTE[hash % ENTITY_TYPE_PALETTE.length];
}

export type EntityColorMap = Map<string, string>;

// Assign each distinct entity type a palette color, in sorted order so the
// mapping is stable for a given set of types. Types beyond the palette length
// wrap around (still deterministic).
export function buildEntityColorMap(types: Iterable<string>): EntityColorMap {
  const distinct = Array.from(new Set(types)).sort();
  const map: EntityColorMap = new Map();
  distinct.forEach((type, index) => {
    map.set(type, ENTITY_TYPE_PALETTE[index % ENTITY_TYPE_PALETTE.length]);
  });
  return map;
}

export function colorForType(type: string, map?: EntityColorMap): string {
  return map?.get(type) ?? hashColor(type);
}
