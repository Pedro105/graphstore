"use client";

import { Bot } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { colorForType } from "@/lib/entity-colors";
import { compactNumber, relativeTime } from "@/lib/format";
import type { SourceActivity } from "@/lib/api";

// Per-agent contribution leaderboard, busiest first: writes, entities/relations
// contributed, share of total writes (as a bar), and last-active. Shared by the
// Overview (compact, top N) and the Agents page (full). Sources come from the
// memory_writes audit log, so this reflects *actual* writers — which may include
// sources that were never formally registered as agents.

function ContributionRow({
  source,
  maxWrites,
}: {
  source: SourceActivity;
  maxWrites: number;
}) {
  const color = colorForType(source.source);
  const share = maxWrites > 0 ? (source.write_count / maxWrites) * 100 : 0;
  return (
    <li className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0">
      <span
        aria-hidden
        className="flex size-7 shrink-0 items-center justify-center rounded-full"
        style={{ backgroundColor: `${color}1a`, color }}
      >
        <Bot className="size-3.5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate font-mono text-xs font-medium text-foreground">
            {source.source}
          </span>
          <span className="shrink-0 text-xs text-muted-foreground">
            {relativeTime(source.last_activity_at)}
          </span>
        </div>
        <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full"
            style={{ width: `${Math.max(share, 4)}%`, backgroundColor: color }}
          />
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {compactNumber(source.write_count)} writes ·{" "}
          {compactNumber(source.entities)} entities ·{" "}
          {compactNumber(source.relations)} relations
        </p>
      </div>
    </li>
  );
}

export function AgentLeaderboard({
  sources,
  loading,
  limit,
  emptyHint,
}: {
  sources: SourceActivity[];
  loading: boolean;
  limit?: number;
  emptyHint?: string;
}) {
  if (loading) {
    return (
      <ul>
        {Array.from({ length: limit ?? 4 }).map((_, i) => (
          <li key={i} className="flex items-center gap-3 py-2.5 first:pt-0">
            <Skeleton className="size-7 shrink-0 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-28" />
              <Skeleton className="h-1.5 w-full" />
              <Skeleton className="h-3 w-40" />
            </div>
          </li>
        ))}
      </ul>
    );
  }

  if (sources.length === 0) {
    return (
      <div className="flex flex-col items-center gap-1 py-8 text-center">
        <p className="text-sm font-medium">No agent activity yet</p>
        <p className="max-w-xs text-sm text-muted-foreground">
          {emptyHint ??
            "Writes are attributed to the source that made them. Once an agent writes, its contribution appears here."}
        </p>
      </div>
    );
  }

  const ranked = [...sources].sort((a, b) => b.write_count - a.write_count);
  const shown = limit ? ranked.slice(0, limit) : ranked;
  const maxWrites = ranked[0]?.write_count ?? 0;

  return (
    <ul>
      {shown.map((source) => (
        <ContributionRow
          key={source.source}
          source={source}
          maxWrites={maxWrites}
        />
      ))}
    </ul>
  );
}
