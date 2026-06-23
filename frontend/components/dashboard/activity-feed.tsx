"use client";

import { ArrowRight, Bot } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { relativeTime } from "@/lib/format";
import { colorForType } from "@/lib/entity-colors";
import type { ActivityItem } from "@/lib/api";

// Recent writes into the graph: which source (agent) wrote, a preview of the
// submitted content, what extraction pulled out, and how long ago. This is the
// multi-agent story made concrete — the thing the product is about.

function ActivityRow({ item }: { item: ActivityItem }) {
  // Color the source dot by treating the source name like a type, so the same
  // agent reads consistently here and in the agent leaderboard.
  const dot = colorForType(item.source);
  return (
    <li className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
      <span
        aria-hidden
        className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full"
        style={{ backgroundColor: `${dot}1a`, color: dot }}
      >
        <Bot className="size-3.5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate font-mono text-xs font-medium text-foreground">
            {item.source}
          </span>
          <span className="shrink-0 text-xs text-muted-foreground">
            {relativeTime(item.created_at)}
          </span>
        </div>
        <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">
          {item.raw_content}
        </p>
        <p className="mt-1 text-xs text-muted-foreground/80">
          +{item.extracted_entity_count} entities · +
          {item.extracted_relation_count} relations
        </p>
      </div>
    </li>
  );
}

export function ActivityFeed({
  items,
  loading,
}: {
  items: ActivityItem[];
  loading: boolean;
}) {
  if (loading) {
    return (
      <ul className="divide-y divide-border">
        {Array.from({ length: 4 }).map((_, i) => (
          <li key={i} className="flex items-start gap-3 py-3 first:pt-0">
            <Skeleton className="size-7 shrink-0 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-32" />
            </div>
          </li>
        ))}
      </ul>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center gap-1 py-8 text-center">
        <p className="text-sm font-medium">No writes yet</p>
        <p className="max-w-xs text-sm text-muted-foreground">
          When an agent writes a memory, it shows up here — with what it
          submitted and what was extracted.
        </p>
        <a
          href="/dashboard/memories"
          className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-data-accent underline-offset-4 hover:underline"
        >
          Write your first memory
          <ArrowRight className="size-3.5" />
        </a>
      </div>
    );
  }

  return (
    <ul className="divide-y divide-border">
      {items.map((item) => (
        <ActivityRow key={item.id} item={item} />
      ))}
    </ul>
  );
}
