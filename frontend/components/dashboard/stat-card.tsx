"use client";

import Link from "next/link";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

// A single headline metric. Optional `accent` paints the value in the data
// accent (for the metric a glance should land on first); optional `href` makes
// the whole card a link. `loading` shows a skeleton in place of the value so a
// cold load keeps the card's shape instead of flashing a dash.
export interface StatCardProps {
  label: string;
  value: number | string | null;
  sublabel?: string;
  href?: string;
  accent?: boolean;
  loading?: boolean;
}

export function StatCard({
  label,
  value,
  sublabel,
  href,
  accent,
  loading,
}: StatCardProps) {
  const body = (
    <div
      className={cn(
        "flex h-full flex-col justify-between gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10 transition-colors",
        href && "hover:bg-muted/40",
      )}
    >
      <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {label}
      </span>
      {loading ? (
        <Skeleton className="h-8 w-16" />
      ) : (
        <span
          className={cn(
            "text-3xl font-semibold tabular-nums",
            accent ? "text-data-accent" : "text-foreground",
          )}
        >
          {value ?? "—"}
        </span>
      )}
      {sublabel ? (
        <span className="text-xs text-muted-foreground">{sublabel}</span>
      ) : null}
    </div>
  );

  return href ? (
    <Link href={href} className="block h-full">
      {body}
    </Link>
  ) : (
    body
  );
}
