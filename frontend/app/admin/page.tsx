"use client";

import Link from "next/link";

import { adminApi } from "@/lib/admin/client";
import { useAdminQuery } from "@/lib/admin/use-admin-query";
import { HBars, MiniBars } from "@/components/admin/charts";
import {
  ErrorRow,
  LoadingRow,
  PageHeading,
  Panel,
  StatCard,
} from "@/components/admin/ui";

function dayLabel(iso: string): string {
  return iso.slice(5); // MM-DD
}

export default function AdminOverviewPage() {
  const users = useAdminQuery((t) => adminApi.listUsers(t));
  const projects = useAdminQuery((t) => adminApi.listProjects(t));
  const analytics = useAdminQuery((t) => adminApi.analytics(t, 30));

  const totalNodes = (projects.data ?? []).reduce(
    (sum, p) => sum + p.node_count,
    0,
  );
  const totalEdges = (projects.data ?? []).reduce(
    (sum, p) => sum + p.edge_count,
    0,
  );
  const a = analytics.data;

  return (
    <div>
      <PageHeading
        title="Operator overview"
        subtitle="Cross-tenant activity, spend, and performance — last 30 days."
      />

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Users" value={users.data?.length ?? "—"} />
        <StatCard label="Projects" value={projects.data?.length ?? "—"} />
        <StatCard
          label="Graph nodes"
          value={projects.data ? totalNodes : "—"}
        />
        <StatCard
          label="Graph edges"
          value={projects.data ? totalEdges : "—"}
        />
      </div>

      {analytics.loading ? (
        <Panel>
          <LoadingRow />
        </Panel>
      ) : analytics.error ? (
        <Panel>
          <ErrorRow message={analytics.error} />
        </Panel>
      ) : a ? (
        <div className="flex flex-col gap-6">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Panel title="Writes per day">
              <div className="p-4">
                <MiniBars
                  points={a.writes_over_time.map((p) => ({
                    label: dayLabel(p.day),
                    value: p.count,
                  }))}
                />
              </div>
            </Panel>
            <Panel title="Token spend per day">
              <div className="p-4">
                <MiniBars
                  points={a.tokens_over_time.map((p) => ({
                    label: dayLabel(p.day),
                    value: p.tokens,
                  }))}
                  format={(n) => n.toLocaleString()}
                />
              </div>
            </Panel>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Panel title="Recall latency p95 (ms) per day">
              <div className="p-4">
                <MiniBars
                  points={a.recall_latency.map((p) => ({
                    label: dayLabel(p.day),
                    value: p.p95 ?? 0,
                    title: `${dayLabel(p.day)}: p50 ${p.p50 ?? "—"}ms · p95 ${p.p95 ?? "—"}ms · ${p.count} recalls`,
                  }))}
                  format={(n) => `${n} ms`}
                />
              </div>
            </Panel>
            <Panel title="Query class breakdown (7d)">
              <div className="p-4">
                <HBars
                  rows={a.query_class_breakdown.map((c) => ({
                    label: (
                      <span className="font-mono text-xs">{c.query_class}</span>
                    ),
                    value: c.count,
                  }))}
                />
              </div>
            </Panel>
          </div>

          <Panel title="Top projects by activity (7d)">
            <div className="p-4">
              <HBars
                rows={(a.top_projects ?? []).map((p) => ({
                  label: (
                    <Link
                      href={`/admin/projects/${p.tenant_id}`}
                      className="hover:underline"
                    >
                      {p.name ?? p.tenant_id}
                    </Link>
                  ),
                  value: p.total,
                  valueLabel: `${p.total} req`,
                  sublabel: `${p.writes} writes · ${p.recalls} recalls`,
                }))}
              />
            </div>
          </Panel>
        </div>
      ) : null}
    </div>
  );
}
