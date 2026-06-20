"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Check, ChevronsUpDown, FolderGit2, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useWorkspace } from "@/lib/dashboard/workspace";
import { cn } from "@/lib/utils";

// Slack/Notion-style workspace switcher at the top of the sidebar. Always shows
// the current project so the operator never loses track of which graph they're
// acting on; the dropdown switches projects (whole dashboard follows) and
// creates new ones.
export function WorkspaceSwitcher() {
  const { projects, activeProject, loading, switchTo, createAndSwitch } =
    useWorkspace();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setCreating(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    const name = newName.trim();
    if (!name || busy) return;
    setBusy(true);
    try {
      await createAndSwitch(name); // reloads on success
    } catch {
      setBusy(false);
    }
  }

  const label = loading ? "Loading…" : (activeProject?.name ?? "No project");

  return (
    <div className="relative mb-4" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-lg border border-border bg-card px-2.5 py-2 text-left text-sm transition-colors hover:bg-muted"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <FolderGit2 className="size-4 shrink-0 text-muted-foreground" />
        <span className="min-w-0 flex-1">
          <span className="block text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
            Project
          </span>
          <span className="block truncate font-medium">{label}</span>
        </span>
        <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" />
      </button>

      {open ? (
        <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-lg border border-border bg-popover shadow-md">
          <ul className="max-h-64 overflow-y-auto py-1" role="listbox">
            {projects.map((p) => {
              const active = p.tenant_id === activeProject?.tenant_id;
              return (
                <li key={p.tenant_id}>
                  <button
                    type="button"
                    onClick={() => switchTo(p.tenant_id)}
                    className={cn(
                      "flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-sm hover:bg-muted",
                      active && "font-medium",
                    )}
                    role="option"
                    aria-selected={active}
                  >
                    <Check
                      className={cn(
                        "size-4 shrink-0",
                        active ? "opacity-100" : "opacity-0",
                      )}
                    />
                    <span className="min-w-0 flex-1 truncate">{p.name}</span>
                    <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                      {p.tenant_id}
                    </span>
                  </button>
                </li>
              );
            })}
            {projects.length === 0 ? (
              <li className="px-2.5 py-1.5 text-sm text-muted-foreground">
                No projects yet.
              </li>
            ) : null}
          </ul>

          <div className="border-t border-border p-1.5">
            {creating ? (
              <form onSubmit={onCreate} className="flex items-center gap-1.5">
                <Input
                  autoFocus
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="New project name"
                  className="h-8 text-sm"
                />
                <Button
                  type="submit"
                  size="sm"
                  disabled={!newName.trim() || busy}
                >
                  {busy ? "…" : "Create"}
                </Button>
              </form>
            ) : (
              <button
                type="button"
                onClick={() => setCreating(true)}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <Plus className="size-4" />
                New project
              </button>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
