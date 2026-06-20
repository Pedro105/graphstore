"use client";

import Link from "next/link";

import { adminApi } from "@/lib/admin/client";
import { useAdminQuery } from "@/lib/admin/use-admin-query";
import {
  EmptyRow,
  ErrorRow,
  LoadingRow,
  PageHeading,
  Panel,
  formatDate,
} from "@/components/admin/ui";

export default function AdminProjectsPage() {
  const { data, error, loading } = useAdminQuery((t) =>
    adminApi.listProjects(t),
  );

  return (
    <div>
      <PageHeading
        title="Projects"
        subtitle="Every project across all users, with live graph stats."
      />
      <Panel>
        {loading ? (
          <LoadingRow />
        ) : error ? (
          <ErrorRow message={error} />
        ) : !data || data.length === 0 ? (
          <EmptyRow>No projects yet.</EmptyRow>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground uppercase">
              <tr className="border-b border-border">
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Owner</th>
                <th className="px-4 py-2 font-medium">Tenant</th>
                <th className="px-4 py-2 text-right font-medium">Nodes</th>
                <th className="px-4 py-2 text-right font-medium">Edges</th>
                <th className="px-4 py-2 font-medium">Last activity</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr
                  key={p.id}
                  className="border-b border-border/50 last:border-0 hover:bg-muted/40"
                >
                  <td className="px-4 py-2 font-medium">
                    <Link
                      href={`/admin/projects/${p.tenant_id}`}
                      className="hover:underline"
                    >
                      {p.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {p.owner_email}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs">{p.tenant_id}</td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {p.node_count}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {p.edge_count}
                  </td>
                  <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">
                    {formatDate(p.last_activity_at)}
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
