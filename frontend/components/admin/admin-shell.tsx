"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode } from "react";
import {
  Activity,
  FolderTree,
  LayoutDashboard,
  LogOut,
  Table2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAdminAuth } from "@/lib/admin/auth";
import { TokenGate } from "@/components/admin/token-gate";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/admin", label: "Overview", icon: LayoutDashboard },
  { href: "/admin/projects", label: "Projects", icon: FolderTree },
  { href: "/admin/facts", label: "Facts", icon: Table2 },
  { href: "/admin/usage", label: "Usage", icon: Activity },
];

function AdminHeader() {
  const pathname = usePathname();
  const { clear } = useAdminAuth();

  return (
    <header className="sticky top-0 z-10 border-b border-amber-500/30 bg-background/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3">
        <Link href="/admin" className="flex items-center gap-2">
          <span className="text-base font-semibold tracking-tight">
            ContextStore
          </span>
          <span className="rounded bg-amber-500 px-1.5 py-0.5 text-[10px] font-bold tracking-widest text-amber-950 uppercase">
            Admin
          </span>
        </Link>
        <nav className="flex items-center gap-1">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active =
              href === "/admin" ? pathname === href : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-amber-500/15 text-amber-700 dark:text-amber-400"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <Icon className="size-4" />
                {label}
              </Link>
            );
          })}
        </nav>
        <Button variant="ghost" size="sm" className="ml-auto" onClick={clear}>
          <LogOut className="size-4" />
          Sign out
        </Button>
      </div>
    </header>
  );
}

// Gates the whole admin area on a *validated* token and frames it with an
// unmistakably distinct (amber, "ADMIN"-badged) chrome so it can never be
// confused with the regular user dashboard. Children (the data pages) render
// only once the backend has confirmed the token (status === "ok") -- so no
// chart/table component mounts or fetches before authentication succeeds.
export function AdminShell({ children }: { children: ReactNode }) {
  const { status } = useAdminAuth();
  if (status !== "ok") return <TokenGate />;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <AdminHeader />
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  );
}
