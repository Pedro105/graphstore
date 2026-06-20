"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

const PAGE_SIZE = 50;

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function AdminFactsPage() {
  const projects = useAdminQuery((t) => adminApi.listProjects(t));

  const [tenantId, setTenantId] = useState("");
  const [source, setSource] = useState("");
  const [includeSuperseded, setIncludeSuperseded] = useState(false);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState(""); // committed search term
  const [page, setPage] = useState(1);

  const facts = useAdminQuery(
    (t) =>
      adminApi.facts(t, {
        tenant_id: tenantId || undefined,
        source: source || undefined,
        include_superseded: includeSuperseded,
        q: query || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
    [tenantId, source, includeSuperseded, query, page],
  );

  const data = facts.data;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  function resetTo(setter: (v: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  return (
    <div>
      <PageHeading
        title="Facts"
        subtitle="Every claim across all projects, flattened and searchable."
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select
          value={tenantId}
          onChange={(e) => resetTo(setTenantId, e.target.value)}
          className="rounded-lg border border-border bg-background px-2 py-1.5 text-sm"
        >
          <option value="">All projects</option>
          {(projects.data ?? []).map((p) => (
            <option key={p.tenant_id} value={p.tenant_id}>
              {p.name}
            </option>
          ))}
        </select>

        <Input
          value={source}
          onChange={(e) => resetTo(setSource, e.target.value)}
          placeholder="Filter by source…"
          className="h-9 w-44"
        />

        <form
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            setQuery(search);
          }}
          className="flex items-center gap-1"
        >
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search entity or value…"
            className="h-9 w-56"
          />
          <Button type="submit" variant="outline" size="sm">
            Search
          </Button>
        </form>

        <label className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={includeSuperseded}
            onChange={(e) => {
              setIncludeSuperseded(e.target.checked);
              setPage(1);
            }}
          />
          Include superseded
        </label>
      </div>

      <Panel>
        {facts.loading ? (
          <LoadingRow />
        ) : facts.error ? (
          <ErrorRow message={facts.error} />
        ) : !data || data.facts.length === 0 ? (
          <EmptyRow>No facts match these filters.</EmptyRow>
        ) : (
          <>
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground uppercase">
                <tr className="border-b border-border">
                  <th className="px-4 py-2 font-medium">Entity</th>
                  <th className="px-4 py-2 font-medium">Property</th>
                  <th className="px-4 py-2 font-medium">Value</th>
                  <th className="px-4 py-2 font-medium">Source</th>
                  <th className="px-4 py-2 font-medium">Project</th>
                  <th className="px-4 py-2 font-medium">Asserted</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.facts.map((f, i) => (
                  <tr
                    key={`${f.entity_id}-${f.property_name}-${f.asserted_at}-${i}`}
                    className="border-b border-border/50 align-top last:border-0"
                  >
                    <td className="px-4 py-2">
                      <span className="font-medium">{f.entity_name}</span>{" "}
                      <span className="text-xs text-muted-foreground">
                        {f.entity_type}
                      </span>
                    </td>
                    <td className="px-4 py-2">{f.property_name ?? "—"}</td>
                    <td className="px-4 py-2 break-words">
                      {renderValue(f.value)}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs">{f.source}</td>
                    <td className="px-4 py-2 font-mono text-xs">
                      {f.tenant_id}
                    </td>
                    <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">
                      {formatDate(f.asserted_at)}
                    </td>
                    <td className="px-4 py-2">
                      {f.superseded ? (
                        <Badge variant="outline">superseded</Badge>
                      ) : (
                        <Badge>active</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="flex items-center justify-between border-t border-border px-4 py-2 text-sm text-muted-foreground">
              <span>
                {data.total} fact{data.total === 1 ? "" : "s"}
                {data.truncated
                  ? " (capped — narrow by project to see all)"
                  : ""}
              </span>
              <span className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Prev
                </Button>
                <span className="tabular-nums">
                  {page} / {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </span>
            </div>
          </>
        )}
      </Panel>
    </div>
  );
}
