"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { Badge } from "@/components/ui/badge";
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

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function AdminEntityClaimsPage() {
  const params = useParams<{ tenant_id: string; entity_id: string }>();
  const { tenant_id: tenantId, entity_id: entityId } = params;

  const { data, error, loading } = useAdminQuery(
    (t) => adminApi.entityClaims(t, tenantId, entityId),
    [tenantId, entityId],
  );

  return (
    <div>
      <PageHeading
        title={data ? data.entity_name : "Claim history"}
        subtitle={
          data
            ? `${data.entity_type} — every claim ever asserted, oldest first`
            : "Provenance / ground-truth view"
        }
      />
      <div className="mb-3 text-sm">
        <Link
          href={`/admin/projects/${tenantId}`}
          className="text-muted-foreground hover:underline"
        >
          ← Back to project
        </Link>
      </div>

      <Panel>
        {loading ? (
          <LoadingRow />
        ) : error ? (
          <ErrorRow message={error} />
        ) : !data || data.claims.length === 0 ? (
          <EmptyRow>No claims recorded for this entity.</EmptyRow>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground uppercase">
              <tr className="border-b border-border">
                <th className="px-4 py-2 font-medium">When</th>
                <th className="px-4 py-2 font-medium">Source</th>
                <th className="px-4 py-2 font-medium">Property</th>
                <th className="px-4 py-2 font-medium">Value</th>
                <th className="px-4 py-2 font-medium">Confidence</th>
                <th className="px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.claims.map(({ claim, superseded }) => (
                <tr
                  key={claim.id}
                  className="border-b border-border/50 last:border-0 align-top"
                >
                  <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">
                    {formatDate(claim.provenance.created_at)}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs">
                    {claim.provenance.source}
                  </td>
                  <td className="px-4 py-2">{claim.property_name ?? "—"}</td>
                  <td className="px-4 py-2 break-words">
                    {renderValue(claim.value)}
                  </td>
                  <td className="px-4 py-2 tabular-nums">
                    {claim.provenance.confidence.toFixed(2)}
                  </td>
                  <td className="px-4 py-2">
                    {superseded ? (
                      <Badge variant="outline">superseded</Badge>
                    ) : (
                      <Badge>active</Badge>
                    )}
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
