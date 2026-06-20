"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

// Small presentational primitives shared across the admin pages. Plain markup
// (no Card subcomponent dependency) so the admin chrome stays self-contained.

export function PageHeading({
  title,
  subtitle,
}: {
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-6">
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      {subtitle ? (
        <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
      ) : null}
    </div>
  );
}

export function StatCard({
  label,
  value,
}: {
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}

export function Panel({
  title,
  children,
  className,
}: {
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn("rounded-xl border border-border bg-card", className)}
    >
      {title ? (
        <div className="border-b border-border px-4 py-3 text-sm font-semibold">
          {title}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function LoadingRow({
  children = "Loading…",
}: {
  children?: ReactNode;
}) {
  return <div className="p-6 text-sm text-muted-foreground">{children}</div>;
}

export function ErrorRow({ message }: { message: string }) {
  return <div className="p-6 text-sm text-destructive">{message}</div>;
}

export function EmptyRow({
  children = "Nothing here yet.",
}: {
  children?: ReactNode;
}) {
  return <div className="p-6 text-sm text-muted-foreground">{children}</div>;
}

export function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}
