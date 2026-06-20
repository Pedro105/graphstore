"use client";

import dynamic from "next/dynamic";

const DemoGraph = dynamic(
  () =>
    import("@/components/landing/demo-graph").then((mod) => mod.DemoGraph),
  {
    ssr: false,
    loading: () => (
      <div className="h-[460px] w-full animate-pulse rounded border border-border bg-muted/40" />
    ),
  },
);

const AGENT_TAGS = [
  { name: "CRM Agent", color: "#6366f1" },
  { name: "Support Agent", color: "#f59e0b" },
  { name: "Product Agent", color: "#10b981" },
  { name: "Account Agent", color: "#8b5cf6" },
];

const ENTITY_LEGEND = [
  { type: "Organization", color: "#6366f1" },
  { type: "Person", color: "#f59e0b" },
  { type: "Service", color: "#10b981" },
  { type: "Release", color: "#8b5cf6" },
  { type: "Date", color: "#3b82f6" },
  { type: "Issue", color: "#ef4444" },
  { type: "Metric", color: "#14b8a6" },
  { type: "Opportunity", color: "#f97316" },
];

export function GraphSection() {
  return (
    <section className="bg-section-alt">
      <div className="mx-auto max-w-6xl px-6 py-20">
        {/* Header */}
        <div className="mb-8 grid items-end gap-6 md:grid-cols-2">
          <div>
            <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Live knowledge graph
            </span>
            <h2 className="mt-2 text-4xl font-light leading-tight text-foreground lg:text-5xl">
              One graph,{" "}
              <span className="italic">built by every agent</span>
            </h2>
          </div>
          <p className="text-base leading-relaxed text-muted-foreground md:text-right">
            Four agents wrote natural language about the same customer account.
            ContextStore extracted entities, resolved them onto shared nodes, and
            built this graph automatically — no schema, no coordination.
          </p>
        </div>

        {/* Who wrote this */}
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted-foreground">Written by:</span>
          {AGENT_TAGS.map((tag) => (
            <span
              key={tag.name}
              className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1 text-sm text-foreground/70"
            >
              <span
                className="size-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: tag.color }}
              />
              {tag.name}
            </span>
          ))}
          <span className="ml-auto rounded border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground">
            8 entities &middot; 8 relations
          </span>
        </div>

        {/* The graph */}
        <DemoGraph />

        {/* Legend */}
        <div className="mt-4 flex flex-wrap items-center gap-5">
          {ENTITY_LEGEND.map((item) => (
            <span
              key={item.type}
              className="flex items-center gap-1.5 text-sm text-muted-foreground"
            >
              <span
                className="size-2 shrink-0 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              {item.type}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
