"use client";

import { Handle, Position, ReactFlow, ReactFlowProvider } from "@xyflow/react";

const ENTITY_COLOR: Record<string, string> = {
  Organization: "#6366f1",
  Person: "#f59e0b",
  Service: "#10b981",
  Release: "#8b5cf6",
  Date: "#3b82f6",
  Issue: "#ef4444",
  Metric: "#14b8a6",
  Opportunity: "#f97316",
};

function DemoNode({
  data,
}: {
  data: { label: string; entityType: string };
}) {
  const color = ENTITY_COLOR[data.entityType] ?? "#78716c";
  return (
    <div className="rounded border border-border bg-card px-3 py-2.5 shadow-sm">
      <Handle
        type="target"
        position={Position.Left}
        style={{ background: color, width: 7, height: 7, border: "none" }}
      />
      <div className="flex items-center gap-2">
        <span
          className="size-2 shrink-0 rounded-full"
          style={{ backgroundColor: color }}
        />
        <span className="max-w-[140px] truncate text-sm font-semibold text-foreground">
          {data.label}
        </span>
      </div>
      <div className="mt-0.5 pl-4 text-xs text-muted-foreground">
        {data.entityType}
      </div>
      <Handle
        type="source"
        position={Position.Right}
        style={{ background: color, width: 7, height: 7, border: "none" }}
      />
    </div>
  );
}

const nodeTypes = { demo: DemoNode };

// B2B SaaS customer success scenario:
// Meridian Corp (enterprise customer) is up for renewal.
// A rate limit bug is blocking their nightly jobs.
// The fix ships in v3.4.0, 6 days before renewal.
// Sofia Reyes (their VP Eng) wants 200 seats more if resolved.
const DEMO_NODES = [
  {
    id: "e1",
    type: "demo",
    position: { x: 0, y: 200 },
    data: { label: "Meridian Corp", entityType: "Organization" },
  },
  {
    id: "e2",
    type: "demo",
    position: { x: 0, y: 60 },
    data: { label: "Sofia Reyes", entityType: "Person" },
  },
  {
    id: "e5",
    type: "demo",
    position: { x: 260, y: 130 },
    data: { label: "Renewal June 30", entityType: "Date" },
  },
  {
    id: "e7",
    type: "demo",
    position: { x: 260, y: 300 },
    data: { label: "$180k ARR", entityType: "Metric" },
  },
  {
    id: "e3",
    type: "demo",
    position: { x: 520, y: 50 },
    data: { label: "Data Export API", entityType: "Service" },
  },
  {
    id: "e6",
    type: "demo",
    position: { x: 520, y: 240 },
    data: { label: "Rate Limit Issue", entityType: "Issue" },
  },
  {
    id: "e4",
    type: "demo",
    position: { x: 780, y: 50 },
    data: { label: "v3.4.0 Release", entityType: "Release" },
  },
  {
    id: "e8",
    type: "demo",
    position: { x: 780, y: 240 },
    data: { label: "$42k Expansion", entityType: "Opportunity" },
  },
];

const edgeStyle = { stroke: "var(--border)", strokeWidth: 1.5 };
const labelStyle = { fontSize: 9, fill: "var(--muted-foreground)", fontFamily: "var(--font-mono)" };
const labelBgStyle = { fill: "var(--card)", opacity: 0.9 };

const DEMO_EDGES = [
  {
    id: "r1",
    source: "e2",
    target: "e1",
    label: "WORKS_AT",
    style: edgeStyle,
    labelStyle,
    labelBgStyle,
  },
  {
    id: "r2",
    source: "e1",
    target: "e5",
    label: "RENEWS_ON",
    style: edgeStyle,
    labelStyle,
    labelBgStyle,
  },
  {
    id: "r3",
    source: "e1",
    target: "e7",
    label: "HAS_ARR",
    style: edgeStyle,
    labelStyle,
    labelBgStyle,
  },
  {
    id: "r4",
    source: "e6",
    target: "e3",
    label: "AFFECTS",
    style: { ...edgeStyle, stroke: "#ef4444" },
    labelStyle: { ...labelStyle, fill: "#ef4444" },
    labelBgStyle,
  },
  {
    id: "r5",
    source: "e4",
    target: "e6",
    label: "FIXES",
    style: { ...edgeStyle, stroke: "#10b981" },
    labelStyle: { ...labelStyle, fill: "#10b981" },
    labelBgStyle,
  },
  {
    id: "r6",
    source: "e2",
    target: "e3",
    label: "MANAGES",
    style: edgeStyle,
    labelStyle,
    labelBgStyle,
  },
  {
    id: "r7",
    source: "e2",
    target: "e8",
    label: "PURSUING",
    style: edgeStyle,
    labelStyle,
    labelBgStyle,
  },
  {
    id: "r8",
    source: "e8",
    target: "e6",
    label: "BLOCKED_BY",
    style: { ...edgeStyle, stroke: "#f97316", strokeDasharray: "4 3" },
    labelStyle: { ...labelStyle, fill: "#f97316" },
    labelBgStyle,
  },
];

export function DemoGraph() {
  return (
    <div className="h-[460px] w-full overflow-hidden rounded border border-border bg-card">
      <ReactFlowProvider>
        <ReactFlow
          nodes={DEMO_NODES}
          edges={DEMO_EDGES}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          proOptions={{ hideAttribution: true }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag
          zoomOnScroll={false}
          zoomOnPinch={false}
        >
          <defs>
            <pattern
              id="landing-dots"
              width="22"
              height="22"
              patternUnits="userSpaceOnUse"
            >
              <circle cx="1" cy="1" r="0.6" fill="var(--border)" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#landing-dots)" />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
