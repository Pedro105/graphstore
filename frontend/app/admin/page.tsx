"use client";

import { adminApi } from "@/lib/admin/client";
import { useAdminQuery } from "@/lib/admin/use-admin-query";
import {
  EmptyRow,
  ErrorRow,
  LoadingRow,
  PageHeading,
  Panel,
  StatCard,
  formatDate,
} from "@/components/admin/ui";

export default function AdminOverviewPage() {
  const users = useAdminQuery((t) => adminApi.listUsers(t));
  const projects = useAdminQuery((t) => adminApi.listProjects(t));
  const usage = useAdminQuery((t) => adminApi.usage(t));

  const totalNodes = (projects.data ?? []).reduce(
    (sum, p) => sum + p.node_count,
    0,
  );
  const totalEdges = (projects.data ?? []).reduce(
    (sum, p) => sum + p.edge_count,
    0,
  );
  const recent = (usage.data ?? []).slice(0, 15);

  return (
    <div>
      <PageHeading
        title="Operator overview"
        subtitle="Cross-tenant view of everything in the store."
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

      <Panel title="Recent activity">
        {usage.loading ? (
          <LoadingRow />
        ) : usage.error ? (
          <ErrorRow message={usage.error} />
        ) : recent.length === 0 ? (
          <EmptyRow>No usage recorded yet.</EmptyRow>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground uppercase">
              <tr className="border-b border-border">
                <th className="px-4 py-2 font-medium">When</th>
                <th className="px-4 py-2 font-medium">Tenant</th>
                <th className="px-4 py-2 font-medium">Endpoint</th>
                <th className="px-4 py-2 text-right font-medium">Tokens</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((row) => (
                <tr
                  key={row.id}
                  className="border-b border-border/50 last:border-0"
                >
                  <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">
                    {formatDate(row.created_at)}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs">
                    {row.tenant_id}
                  </td>
                  <td className="px-4 py-2">{row.endpoint}</td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {row.tokens_used ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
