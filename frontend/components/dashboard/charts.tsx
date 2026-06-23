"use client";

import { useMemo } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CHART, QUERY_CLASS_COLORS } from "@/lib/chart-theme";
import type {
  ClassCount,
  LatencyPoint,
  UsageDayPoint,
  WritePoint,
} from "@/lib/api";

// Shared chart primitives for the Overview. Each takes already-fetched data and
// is purely presentational; loading/empty handling lives in the parent so these
// stay simple and reusable.

function formatDay(day: string): string {
  // day is an ISO date (YYYY-MM-DD); render as "Jun 3" without timezone drift.
  const [y, m, d] = day.split("-").map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

const AXIS_PROPS = {
  stroke: CHART.axis,
  fontSize: 11,
  tickLine: false,
  axisLine: false,
} as const;

interface TooltipEntry {
  name?: string;
  value?: number | string;
  color?: string;
}

function ChartTooltip({
  active,
  label,
  payload,
  suffix,
}: {
  active?: boolean;
  label?: string;
  payload?: TooltipEntry[];
  suffix?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      {label ? (
        <p className="mb-1 font-medium text-foreground">{formatDay(label)}</p>
      ) : null}
      <div className="flex flex-col gap-0.5">
        {payload.map((entry) => (
          <div
            key={entry.name}
            className="flex items-center justify-between gap-4"
          >
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <span
                aria-hidden
                className="size-2 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              {entry.name}
            </span>
            <span className="font-mono tabular-nums text-foreground">
              {entry.value}
              {suffix ?? ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Writes (memory_writes) vs recalls (usage_log) per day, as a filled-area + line
// composed chart so two series of different magnitudes stay legible.
export function WritesRecallsChart({
  writes,
  recallCounts,
}: {
  writes: WritePoint[];
  recallCounts: { day: string; recalls: number }[];
}) {
  const data = useMemo(() => {
    const byDay = new Map<
      string,
      { day: string; writes: number; recalls: number }
    >();
    for (const point of writes) {
      byDay.set(point.day, { day: point.day, writes: point.count, recalls: 0 });
    }
    for (const point of recallCounts) {
      const existing = byDay.get(point.day);
      if (existing) existing.recalls = point.recalls;
      else
        byDay.set(point.day, {
          day: point.day,
          writes: 0,
          recalls: point.recalls,
        });
    }
    return Array.from(byDay.values()).sort((a, b) =>
      a.day.localeCompare(b.day),
    );
  }, [writes, recallCounts]);

  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart
        data={data}
        margin={{ top: 8, right: 8, bottom: 0, left: -16 }}
      >
        <defs>
          <linearGradient id="writesFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART.writes} stopOpacity={0.22} />
            <stop offset="100%" stopColor={CHART.writes} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={CHART.grid} vertical={false} />
        <XAxis
          dataKey="day"
          tickFormatter={formatDay}
          minTickGap={24}
          {...AXIS_PROPS}
        />
        <YAxis allowDecimals={false} width={36} {...AXIS_PROPS} />
        <Tooltip content={<ChartTooltip />} cursor={{ stroke: CHART.grid }} />
        <Area
          type="monotone"
          dataKey="writes"
          name="Writes"
          stroke={CHART.writes}
          strokeWidth={2}
          fill="url(#writesFill)"
        />
        <Line
          type="monotone"
          dataKey="recalls"
          name="Recalls"
          stroke={CHART.recalls}
          strokeWidth={2}
          dot={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// Recall latency p50/p95 over time, compact, for the "recall performance" card.
export function LatencyChart({ latency }: { latency: LatencyPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={120}>
      <ComposedChart
        data={latency}
        margin={{ top: 6, right: 8, bottom: 0, left: -20 }}
      >
        <CartesianGrid stroke={CHART.grid} vertical={false} />
        <XAxis
          dataKey="day"
          tickFormatter={formatDay}
          minTickGap={28}
          {...AXIS_PROPS}
        />
        <YAxis allowDecimals={false} width={36} {...AXIS_PROPS} />
        <Tooltip
          content={<ChartTooltip suffix="ms" />}
          cursor={{ stroke: CHART.grid }}
        />
        <Line
          type="monotone"
          dataKey="p50"
          name="p50"
          stroke={CHART.p50}
          strokeWidth={2}
          dot={false}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="p95"
          name="p95"
          stroke={CHART.p95}
          strokeWidth={2}
          strokeDasharray="4 3"
          dot={false}
          connectNulls
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// Daily recalls + writes as two overlaid areas, for the Usage page. Sorted by
// date; only days with real activity are present (no zero-filled phantoms).
export function UsageAreaChart({ byDay }: { byDay: UsageDayPoint[] }) {
  const data = useMemo(
    () => [...byDay].sort((a, b) => a.date.localeCompare(b.date)),
    [byDay],
  );

  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart
        data={data}
        margin={{ top: 8, right: 8, bottom: 0, left: -16 }}
      >
        <defs>
          <linearGradient id="recallsArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART.recalls} stopOpacity={0.25} />
            <stop offset="100%" stopColor={CHART.recalls} stopOpacity={0} />
          </linearGradient>
          <linearGradient id="writesArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART.writes} stopOpacity={0.25} />
            <stop offset="100%" stopColor={CHART.writes} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={CHART.grid} vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={formatDay}
          minTickGap={24}
          {...AXIS_PROPS}
        />
        <YAxis allowDecimals={false} width={36} {...AXIS_PROPS} />
        <Tooltip content={<ChartTooltip />} cursor={{ stroke: CHART.grid }} />
        <Area
          type="monotone"
          dataKey="recalls"
          name="Recalls"
          stroke={CHART.recalls}
          strokeWidth={2}
          fill="url(#recallsArea)"
        />
        <Area
          type="monotone"
          dataKey="writes"
          name="Writes"
          stroke={CHART.writes}
          strokeWidth={2}
          fill="url(#writesArea)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

const QUERY_CLASS_LABELS: Record<string, string> = {
  exact_lookup: "Exact lookup",
  single_hop: "Single hop",
  relational: "Relational",
  manual: "Manual",
};

// Recall query-class mix as a horizontal bar list — how the classifier routed
// recent queries (exact lookup vs single-hop vs relational).
export function QueryClassChart({ classes }: { classes: ClassCount[] }) {
  const data = useMemo(
    () =>
      classes.map((c) => ({
        label: QUERY_CLASS_LABELS[c.query_class] ?? c.query_class,
        count: c.count,
        fill: QUERY_CLASS_COLORS[c.query_class] ?? CHART.axis,
      })),
    [classes],
  );

  return (
    <ResponsiveContainer width="100%" height={Math.max(80, data.length * 34)}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 0, right: 12, bottom: 0, left: 0 }}
        barCategoryGap={8}
      >
        <XAxis type="number" hide allowDecimals={false} />
        <YAxis type="category" dataKey="label" width={90} {...AXIS_PROPS} />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: "transparent" }} />
        <Bar
          dataKey="count"
          name="Recalls"
          radius={[0, 4, 4, 0]}
          isAnimationActive={false}
        >
          {data.map((entry) => (
            <Cell key={entry.label} fill={entry.fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
