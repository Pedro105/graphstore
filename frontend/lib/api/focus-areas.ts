// Local feature: focus areas (domains/scopes memory can be organized
// around). No backend yet -- persisted locally, same swap-later shape as
// agents.ts.

import { generateId, readLocal, writeLocal } from "@/lib/api/local-store";
import type { FocusArea } from "@/lib/api/local-types";

const STORAGE_KEY = "contextstore.focus-areas";

function load(): FocusArea[] {
  return readLocal<FocusArea[]>(STORAGE_KEY, []);
}

function save(focusAreas: FocusArea[]): void {
  writeLocal(STORAGE_KEY, focusAreas);
}

export async function listFocusAreas(): Promise<FocusArea[]> {
  return load();
}

export async function createFocusArea(
  input: Omit<FocusArea, "id" | "created_at">,
): Promise<FocusArea> {
  const focusArea: FocusArea = {
    ...input,
    id: generateId("focus"),
    created_at: new Date().toISOString(),
  };
  save([...load(), focusArea]);
  return focusArea;
}

export async function updateFocusArea(
  id: string,
  patch: Partial<Omit<FocusArea, "id">>,
): Promise<FocusArea> {
  const focusAreas = load();
  const index = focusAreas.findIndex((focusArea) => focusArea.id === id);
  if (index === -1) throw new Error(`Focus area ${id} not found`);
  const updated = { ...focusAreas[index], ...patch };
  focusAreas[index] = updated;
  save(focusAreas);
  return updated;
}

export async function deleteFocusArea(id: string): Promise<void> {
  save(load().filter((focusArea) => focusArea.id !== id));
}
