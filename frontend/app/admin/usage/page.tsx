"use client";

import { useState } from "react";

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

export default function AdminUsagePage() {
  const [tenantFilter, setTenantFilter] = useState("");

  const projects = useAdminQuery((t) => adminApi.listProjects(t));
  const usage = useAdminQuery(
    (t) => adminApi.usage(t, tenantFilter || undefined),
    [tenantFilter],
  );

  const totalTokens = (usage.data ?? []).reduce(
    (sum, r) => sum + (r.tokens_used ?? 0),
    0,
  );

  return (
    <div>
      <PageHeading
        title="Usage"
        subtitle="Per-request usage log across all tenants."
      />

      <div className="mb-4 flex items-center gap-3">
        <label
          className="text-sm text-muted-foreground"
          htmlFor="tenant-filter"
        >
          Tenant
        </label>
        <select
          id="tenant-filter"
          value={tenantFilter}
          onChange={(e) => setTenantFilter(e.target.value)}
          className="rounded-lg border border-border bg-background px-2 py-1.5 text-sm"
        >
          <option value="">All tenants</option>
          {(projects.data ?? []).map((p) => (
            <option key={p.tenant_id} value={p.tenant_id}>
              {p.name} ({p.tenant_id})
            </option>
          ))}
        </select>
        <span className="ml-auto text-sm text-muted-foreground">
          Σ tokens:{" "}
          <span className="tabular-nums">{totalTokens.toLocaleString()}</span>
        </span>
      </div>

      <Panel>
        {usage.loading ? (
          <LoadingRow />
        ) : usage.error ? (
          <ErrorRow message={usage.error} />
        ) : !usage.data || usage.data.length === 0 ? (
          <EmptyRow>No usage recorded.</EmptyRow>
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
              {usage.data.map((row) => (
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
