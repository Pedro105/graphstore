"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ChevronsUpDown,
  ExternalLink,
  FileText,
  KeyRound,
  Settings,
  UserRound,
} from "lucide-react";

import { useWorkspace } from "@/lib/dashboard/workspace";
import { DOCS_URL } from "@/lib/links";

// Bottom-left account affordance, the slot where Claude/Notion/Linear put the
// user menu. ContextStore has no per-user login yet (the dashboard runs on one
// shared server-side API key -- see lib/api/fastapi.ts), so this menu only
// exposes what's real: docs, API keys, and the current project context. It does
// NOT show an email or a Sign out, because there is no session to reflect or end
// -- that's a future task gated on building real dashboard auth.
export function AccountMenu() {
  const { activeProject, loading } = useWorkspace();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const projectLabel = loading
    ? "Loading…"
    : (activeProject?.name ?? "No project");

  return (
    <div className="relative mt-auto pt-4" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-lg border border-border bg-card px-2.5 py-2 text-left text-sm transition-colors hover:bg-muted"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-accent text-accent-foreground">
          <UserRound className="size-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">Account</span>
          <span className="block truncate text-[11px] text-muted-foreground">
            Self-hosted
          </span>
        </span>
        <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" />
      </button>

      {open ? (
        <div className="absolute bottom-full left-0 z-20 mb-1 w-full overflow-hidden rounded-lg border border-border bg-popover shadow-md">
          <div className="border-b border-border px-3 py-2.5">
            <p className="text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
              Active project
            </p>
            <p className="mt-0.5 truncate text-sm font-medium">{projectLabel}</p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              Self-hosted · Free tier
            </p>
          </div>

          <div className="py-1">
            <Link
              href="/dashboard/settings"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <Settings className="size-4 shrink-0" />
              <span className="flex-1">Settings</span>
            </Link>
            <Link
              href="/dashboard/api-keys"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <KeyRound className="size-4 shrink-0" />
              <span className="flex-1">API keys</span>
            </Link>
            <a
              href={DOCS_URL}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <FileText className="size-4 shrink-0" />
              <span className="flex-1">Documentation</span>
              <ExternalLink className="size-3.5 shrink-0 opacity-60" />
            </a>
          </div>

          <div className="border-t border-border px-3 py-2">
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              Personal accounts &amp; sign-out are coming soon.
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
