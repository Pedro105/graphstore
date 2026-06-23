"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart2,
  Database,
  KeyRound,
  LayoutDashboard,
  Target,
  Users,
  Workflow,
} from "lucide-react";

import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/memories", label: "Memories", icon: Database },
  { href: "/dashboard/agents", label: "Agents", icon: Users },
  { href: "/dashboard/frameworks", label: "Frameworks", icon: Workflow },
  { href: "/dashboard/focus-areas", label: "Focus Areas", icon: Target },
  { href: "/dashboard/api-keys", label: "APIs", icon: KeyRound },
  { href: "/dashboard/usage", label: "Usage", icon: BarChart2 },
];

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col gap-1">
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const active =
          href === "/dashboard" ? pathname === href : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className="size-4" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
