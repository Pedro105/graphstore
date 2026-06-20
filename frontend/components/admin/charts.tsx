"use client";

import type { ReactNode } from "react";

// Dependency-free charts (plain CSS bars) for the admin analytics panels. Kept
// deliberately small -- the dashboard needs trend-at-a-glance, not a plotting
// library.

export function MiniBars({
  points,
  format,
  className,
}: {
  points: { label: string; value: number; title?: string }[];
  format?: (n: number) => string;
  className?: string;
}) {
  const max = Math.max(1, ...points.map((p) => p.value));
  return (
    <div className={className}>
      <div className="flex h-28 items-end gap-px">
        {points.length === 0 ? (
          <div className="flex w-full items-center justify-center text-xs text-muted-foreground">
            No data in range.
          </div>
        ) : (
          points.map((p, i) => (
            <div
              key={i}
              className="min-w-0 flex-1"
              title={
                p.title ?? `${p.label}: ${format ? format(p.value) : p.value}`
              }
            >
              <div
                className="w-full rounded-t-sm bg-amber-500/70 transition-colors hover:bg-amber-500"
                style={{
                  height: `${Math.max((p.value / max) * 100, p.value > 0 ? 4 : 0)}%`,
                }}
              />
            </div>
          ))
        )}
      </div>
      {points.length > 0 ? (
        <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
          <span>{points[0].label}</span>
          <span>{points[points.length - 1].label}</span>
        </div>
      ) : null}
    </div>
  );
}

export function HBars({
  rows,
}: {
  rows: {
    label: ReactNode;
    value: number;
    valueLabel?: string;
    sublabel?: ReactNode;
  }[];
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  if (rows.length === 0) {
    return <div className="text-sm text-muted-foreground">No data.</div>;
  }
  return (
    <div className="flex flex-col gap-2.5">
      {rows.map((r, i) => (
        <div key={i}>
          <div className="flex items-baseline justify-between gap-2 text-sm">
            <span className="min-w-0 truncate">{r.label}</span>
            <span className="shrink-0 tabular-nums text-muted-foreground">
              {r.valueLabel ?? r.value}
            </span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-amber-500"
              style={{ width: `${(r.value / max) * 100}%` }}
            />
          </div>
          {r.sublabel ? (
            <div className="mt-0.5 text-xs text-muted-foreground">
              {r.sublabel}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
