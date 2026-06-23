"use client";

import { Bot, CreditCard, Info, Zap } from "lucide-react";

import { UsageAreaChart } from "@/components/dashboard/charts";
import { StatCard } from "@/components/dashboard/stat-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { CHART } from "@/lib/chart-theme";
import { compactNumber, relativeTime } from "@/lib/format";
import { estimatedCost, formatCost, HAIKU_USD_PER_MTOK } from "@/lib/pricing";
import { useUsage } from "@/lib/hooks/use-observability";
import type { EndpointUsage } from "@/lib/api";

const COST_TOOLTIP = `Based on estimated Claude Haiku token pricing (~$${HAIKU_USD_PER_MTOK.toFixed(2)} / million tokens). Actual costs may vary.`;

function Panel({
  title,
  description,
  action,
  children,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
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

// The estimated-cost stat needs an info affordance the generic StatCard lacks.
function CostStat({
  value,
  loading,
}: {
  value: string | null;
  loading: boolean;
}) {
  return (
    <div className="flex h-full flex-col justify-between gap-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <span className="flex items-center gap-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Est. cost
        <Popover>
          <PopoverTrigger
            aria-label="About this estimate"
            className="inline-flex items-center text-muted-foreground transition-colors hover:text-foreground"
          >
            <Info className="size-3.5" />
          </PopoverTrigger>
          <PopoverContent className="text-xs">{COST_TOOLTIP}</PopoverContent>
        </Popover>
      </span>
      {loading ? (
        <Skeleton className="h-8 w-20" />
      ) : (
        <span className="text-3xl font-semibold tabular-nums text-data-accent">
          {value ?? "—"}
        </span>
      )}
      <span className="text-xs text-muted-foreground">
        estimate · this month
      </span>
    </div>
  );
}

function CostBreakdown({
  byEndpoint,
}: {
  byEndpoint: Record<string, EndpointUsage>;
}) {
  const memories = byEndpoint["/v1/memories"] ?? { calls: 0, tokens: 0 };
  const recall = byEndpoint["/v1/recall"] ?? { calls: 0, tokens: 0 };
  const rows = [
    { label: "/v1/memories", unit: "writes", usage: memories },
    { label: "/v1/recall", unit: "recalls", usage: recall },
  ];
  const totalCalls = memories.calls + recall.calls;
  const totalTokens = memories.tokens + recall.tokens;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="py-2 font-medium">Endpoint</th>
            <th className="py-2 text-right font-medium">Calls</th>
            <th className="py-2 text-right font-medium">Tokens</th>
            <th className="py-2 text-right font-medium">Est. cost</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-border/60">
              <td className="py-2.5 font-mono text-xs">{row.label}</td>
              <td className="py-2.5 text-right tabular-nums">
                {compactNumber(row.usage.calls)}{" "}
                <span className="text-xs text-muted-foreground">
                  {row.unit}
                </span>
              </td>
              <td className="py-2.5 text-right tabular-nums">
                {compactNumber(row.usage.tokens)}
              </td>
              <td className="py-2.5 text-right tabular-nums">
                ~{formatCost(estimatedCost(row.usage.tokens))}
              </td>
            </tr>
          ))}
          <tr className="font-medium">
            <td className="py-2.5">Total</td>
            <td className="py-2.5 text-right tabular-nums">
              {compactNumber(totalCalls)}
            </td>
            <td className="py-2.5 text-right tabular-nums">
              {compactNumber(totalTokens)}
            </td>
            <td className="py-2.5 text-right tabular-nums text-data-accent">
              ~{formatCost(estimatedCost(totalTokens))}
            </td>
          </tr>
        </tbody>
      </table>
      <p className="mt-3 text-xs text-muted-foreground">{COST_TOOLTIP}</p>
    </div>
  );
}

function BillingCard() {
  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <CreditCard className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-heading text-base font-semibold tracking-tight">
              Billing
            </h2>
            <span className="inline-flex items-center rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
              Early access
            </span>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Usage is tracked; billing is not yet active.
          </p>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground">Current plan</p>
              <p className="mt-0.5 text-sm font-medium">Early access</p>
              <p className="text-xs text-muted-foreground">
                Usage tracked, billing not yet active
              </p>
            </div>
            <div className="rounded-lg border border-border bg-muted/30 p-3">
              <p className="flex items-center gap-1 text-xs text-muted-foreground">
                Credit balance
                <span title="Billing coming soon" className="cursor-help">
                  <Info className="size-3" />
                </span>
              </p>
              <p className="mt-0.5 text-sm font-medium text-muted-foreground">
                —
              </p>
              <p className="text-xs text-muted-foreground">
                Billing coming soon
              </p>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <span
              title="Stripe integration coming soon"
              className="inline-flex"
            >
              <Button variant="outline" size="sm" disabled>
                Manage billing
              </Button>
            </span>
            <p className="text-xs text-muted-foreground">
              You&apos;ll be notified before billing goes live. Current usage is
              being tracked and will inform your plan.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

export default function UsagePage() {
  const { usage, loading, error, reload } = useUsage();

  const periodLabel = usage
    ? new Date(`${usage.period}-01T00:00:00Z`).toLocaleDateString(undefined, {
        month: "long",
        year: "numeric",
        timeZone: "UTC",
      })
    : null;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Usage</h1>
        <p className="text-muted-foreground">
          {periodLabel
            ? `Consumption for ${periodLabel}, scoped to this project.`
            : "Consumption for this project."}
        </p>
      </div>

      {error ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <p className="max-w-sm text-sm text-destructive">{error}</p>
            <Button size="sm" variant="outline" onClick={() => void reload()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* This month at a glance */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard
              label="Recalls · month"
              value={usage ? usage.total_recalls.toLocaleString() : null}
              loading={loading && !usage}
            />
            <StatCard
              label="Writes · month"
              value={usage ? usage.total_writes.toLocaleString() : null}
              loading={loading && !usage}
            />
            <StatCard
              label="Tokens · month"
              value={usage ? compactNumber(usage.tokens_used) : null}
              loading={loading && !usage}
            />
            <CostStat
              value={usage ? `~${formatCost(usage.estimated_cost_usd)}` : null}
              loading={loading && !usage}
            />
          </div>

          {/* Activity over time */}
          <Panel
            title="Activity over time"
            description="Daily recalls and writes over the last 30 days"
            action={
              <div className="flex gap-3">
                <LegendDot color={CHART.recalls} label="Recalls" />
                <LegendDot color={CHART.writes} label="Writes" />
              </div>
            }
          >
            {loading && !usage ? (
              <Skeleton className="h-[260px] w-full" />
            ) : usage && usage.by_day.length > 0 ? (
              <UsageAreaChart byDay={usage.by_day} />
            ) : (
              <div className="flex h-[260px] flex-col items-center justify-center gap-1 text-center">
                <Zap className="size-5 text-muted-foreground" />
                <p className="text-sm font-medium">No activity yet</p>
                <p className="max-w-xs text-sm text-muted-foreground">
                  Recalls and writes will chart here once your agents start
                  using the store.
                </p>
              </div>
            )}
          </Panel>

          {/* Cost breakdown */}
          <Panel
            title="Cost breakdown"
            description="Estimated, by endpoint, this month"
          >
            {loading && !usage ? (
              <Skeleton className="h-28 w-full" />
            ) : usage ? (
              <CostBreakdown byEndpoint={usage.by_endpoint} />
            ) : null}
          </Panel>

          {/* Agent contribution */}
          <Panel
            title="Agent contribution"
            description="Writes attributed per source"
          >
            {loading && !usage ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : usage && usage.by_agent.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs text-muted-foreground">
                      <th className="py-2 font-medium">Agent</th>
                      <th className="py-2 text-right font-medium">Writes</th>
                      <th className="py-2 text-right font-medium">
                        Last active
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...usage.by_agent]
                      .sort((a, b) => b.writes - a.writes)
                      .map((agent) => (
                        <tr
                          key={agent.source}
                          className="border-b border-border/60"
                        >
                          <td className="flex items-center gap-2 py-2.5">
                            <Bot className="size-3.5 text-muted-foreground" />
                            <span className="font-mono text-xs">
                              {agent.source}
                            </span>
                          </td>
                          <td className="py-2.5 text-right tabular-nums">
                            {compactNumber(agent.writes)}
                          </td>
                          <td className="py-2.5 text-right text-muted-foreground">
                            {relativeTime(agent.last_active)}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-1 py-8 text-center">
                <Bot className="size-5 text-muted-foreground" />
                <p className="text-sm font-medium">
                  No agent activity recorded yet
                </p>
                <p className="max-w-sm text-sm text-muted-foreground">
                  Agents are identified by the{" "}
                  <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">
                    source
                  </code>{" "}
                  field on memory writes.
                </p>
              </div>
            )}
          </Panel>

          <BillingCard />
        </>
      )}
    </div>
  );
}
