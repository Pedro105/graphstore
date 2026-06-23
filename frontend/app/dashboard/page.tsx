"use client";

import { useMemo } from "react";
import Link from "next/link";
import { ArrowRight, Bot, Database, Gauge, Zap } from "lucide-react";

import { ActivityFeed } from "@/components/dashboard/activity-feed";
import { AgentLeaderboard } from "@/components/dashboard/agent-leaderboard";
import {
  LatencyChart,
  QueryClassChart,
  WritesRecallsChart,
} from "@/components/dashboard/charts";
import { StatCard } from "@/components/dashboard/stat-card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchGraph } from "@/lib/api";
import type { GraphSnapshot } from "@/lib/api";
import { CHART } from "@/lib/chart-theme";
import { compactNumber } from "@/lib/format";
import {
  useActivity,
  useAnalytics,
  useSources,
} from "@/lib/hooks/use-observability";
import { useCachedResource } from "@/lib/hooks/use-cached-resource";
import { useWorkspace } from "@/lib/dashboard/workspace";

function sum(values: number[]): number {
  return values.reduce((a, b) => a + b, 0);
}

// A titled panel with an optional header action (e.g. a "View all" link).
function Panel({
  title,
  description,
  action,
  children,
  className,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-xl bg-card p-5 ring-1 ring-foreground/10 ${className ?? ""}`}
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-base font-semibold tracking-tight">
            {title}
          </h2>
          {description ? (
            <p className="mt-0.5 text-xs text-muted-foreground">
              {description}
            </p>
          ) : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <span
        aria-hidden
        className="size-2 rounded-full"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}

export default function DashboardPage() {
  const { activeProject } = useWorkspace();
  const { data: graph } = useCachedResource<GraphSnapshot>("graph", fetchGraph);
  const { analytics, loading: analyticsLoading } = useAnalytics();
  const { activity, loading: activityLoading } = useActivity();
  const { sources, loading: sourcesLoading } = useSources();

  const entities = graph?.entities.length ?? null;
  const relations = graph?.relations.length ?? null;

  const recallCounts = useMemo(
    () =>
      (analytics?.recall_latency ?? []).map((p) => ({
        day: p.day,
        recalls: p.count,
      })),
    [analytics],
  );

  const writes30d = analytics
    ? sum(analytics.writes_over_time.map((p) => p.count))
    : null;
  const recalls30d = analytics
    ? sum(analytics.recall_latency.map((p) => p.count))
    : null;
  const tokens30d = analytics
    ? sum(analytics.tokens_over_time.map((p) => p.tokens))
    : null;

  // Latest day with recall data carries the "current" latency numbers.
  const latestLatency = useMemo(() => {
    const withData = (analytics?.recall_latency ?? []).filter(
      (p) => p.p50 !== null,
    );
    return withData.length ? withData[withData.length - 1] : null;
  }, [analytics]);

  const activeAgents24h = useMemo(() => {
    const cutoff = Date.now() - 24 * 60 * 60 * 1000;
    return sources.filter(
      (s) => new Date(s.last_activity_at).getTime() >= cutoff,
    ).length;
  }, [sources]);

  const hasActivity =
    (analytics?.writes_over_time.length ?? 0) > 0 || activity.length > 0;
  const hasLatency = (analytics?.recall_latency ?? []).some(
    (p) => p.p50 !== null,
  );
  const hasClasses = (analytics?.query_class_breakdown.length ?? 0) > 0;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
        <p className="text-muted-foreground">
          {activeProject ? (
            <>
              What&apos;s happening in{" "}
              <span className="font-medium text-foreground">
                {activeProject.name}
              </span>
              .
            </>
          ) : (
            "What's happening across your memory workspace."
          )}
        </p>
      </div>

      {/* Headline metrics: graph size + recent throughput. */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Entities"
          value={entities}
          href="/dashboard/memories"
          loading={graph === null}
        />
        <StatCard
          label="Relations"
          value={relations}
          href="/dashboard/memories"
          loading={graph === null}
        />
        <StatCard
          label="Writes · 30d"
          value={writes30d}
          sublabel={
            activeAgents24h > 0
              ? `${activeAgents24h} agents active in 24h`
              : undefined
          }
          accent
          loading={analyticsLoading && !analytics}
        />
        <StatCard
          label="Recalls · 30d"
          value={recalls30d}
          sublabel={
            tokens30d !== null
              ? `${compactNumber(tokens30d)} tokens used`
              : undefined
          }
          loading={analyticsLoading && !analytics}
        />
      </div>

      {/* Activity over time + most active agents. */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
        <Panel
          title="Write & recall activity"
          description="Daily writes and recalls over the last 30 days"
          action={
            <div className="flex gap-3">
              <LegendDot color={CHART.writes} label="Writes" />
              <LegendDot color={CHART.recalls} label="Recalls" />
            </div>
          }
        >
          {analyticsLoading && !analytics ? (
            <Skeleton className="h-[220px] w-full" />
          ) : hasActivity ? (
            <WritesRecallsChart
              writes={analytics?.writes_over_time ?? []}
              recallCounts={recallCounts}
            />
          ) : (
            <div className="flex h-[220px] flex-col items-center justify-center gap-1 text-center">
              <Zap className="size-5 text-muted-foreground" />
              <p className="text-sm font-medium">No activity yet</p>
              <p className="max-w-xs text-sm text-muted-foreground">
                Writes and recalls will chart here as your agents start using
                the store.
              </p>
            </div>
          )}
        </Panel>

        <Panel
          title="Most active agents"
          description="By writes contributed"
          action={
            <Link
              href="/dashboard/agents"
              className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
            >
              All agents
              <ArrowRight className="size-3" />
            </Link>
          }
        >
          <AgentLeaderboard
            sources={sources}
            loading={sourcesLoading && sources.length === 0}
            limit={5}
          />
        </Panel>
      </div>

      {/* Recent activity feed + recall performance. */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
        <Panel
          title="Recent activity"
          description="Latest writes into the graph"
          action={
            <Link
              href="/dashboard/memories"
              className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
            >
              Memories
              <ArrowRight className="size-3" />
            </Link>
          }
        >
          <ActivityFeed
            items={activity.slice(0, 8)}
            loading={activityLoading && activity.length === 0}
          />
        </Panel>

        <Panel
          title="Recall performance"
          description="Latency & how queries were routed"
        >
          {analyticsLoading && !analytics ? (
            <div className="space-y-4">
              <Skeleton className="h-[120px] w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : hasLatency || hasClasses ? (
            <div className="space-y-4">
              {hasLatency ? (
                <div>
                  <div className="mb-1 flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Gauge className="size-3.5" /> Recall latency
                    </span>
                    {latestLatency ? (
                      <span className="font-mono text-xs tabular-nums text-foreground">
                        p50 {latestLatency.p50}ms · p95 {latestLatency.p95}ms
                      </span>
                    ) : null}
                  </div>
                  <LatencyChart latency={analytics?.recall_latency ?? []} />
                </div>
              ) : null}
              {hasClasses ? (
                <div>
                  <span className="text-xs text-muted-foreground">
                    Query routing · last 7 days
                  </span>
                  <div className="mt-1">
                    <QueryClassChart
                      classes={analytics?.query_class_breakdown ?? []}
                    />
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="flex flex-col items-center gap-1 py-8 text-center">
              <Gauge className="size-5 text-muted-foreground" />
              <p className="text-sm font-medium">No recalls yet</p>
              <p className="max-w-xs text-sm text-muted-foreground">
                Run a recall from the Memories workspace to see latency and
                routing here.
              </p>
            </div>
          )}
        </Panel>
      </div>

      {/* Onboarding nudge only while the graph is genuinely empty. */}
      {graph !== null && entities === 0 && !hasActivity ? (
        <section className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
          <div className="flex items-start gap-4">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-data-accent-soft text-data-accent">
              <Database className="size-5" />
            </span>
            <div>
              <h2 className="font-heading text-base font-semibold">
                Get started
              </h2>
              <p className="mt-0.5 max-w-lg text-sm text-muted-foreground">
                Write a fact in the Memories workspace and watch the graph grow,
                then register the agents that will write into it.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Link
                  href="/dashboard/memories"
                  className="inline-flex items-center gap-1.5 rounded-lg bg-data-accent px-3 py-1.5 text-sm font-medium text-data-accent-foreground hover:opacity-90"
                >
                  <Database className="size-4" /> Open Memories
                </Link>
                <Link
                  href="/dashboard/agents"
                  className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-muted-foreground ring-1 ring-border hover:bg-muted"
                >
                  <Bot className="size-4" /> Register agents
                </Link>
              </div>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}
