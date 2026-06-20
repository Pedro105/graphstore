"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { MemoryGraph } from "@/components/memories/memory-graph";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { adminApi, AdminApiError } from "@/lib/admin/client";
import { useAdminAuth } from "@/lib/admin/auth";
import { useAdminQuery } from "@/lib/admin/use-admin-query";
import type { GraphSnapshot } from "@/lib/admin/types";
import {
  EmptyRow,
  ErrorRow,
  LoadingRow,
  PageHeading,
  Panel,
  StatCard,
  formatDate,
} from "@/components/admin/ui";

export default function AdminProjectDetailPage() {
  const params = useParams<{ tenant_id: string }>();
  const tenantId = params.tenant_id;
  const router = useRouter();
  const { token } = useAdminAuth();

  const projects = useAdminQuery((t) => adminApi.listProjects(t));
  const memories = useAdminQuery(
    (t) => adminApi.projectMemories(t, tenantId),
    [tenantId],
  );
  const sources = useAdminQuery(
    (t) => adminApi.projectSources(t, tenantId),
    [tenantId],
  );

  const project = (projects.data ?? []).find((p) => p.tenant_id === tenantId);

  // The live graph is loaded only on demand (it's a full snapshot).
  const [graph, setGraph] = useState<GraphSnapshot | null>(null);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);

  async function loadGraph() {
    if (!token) return;
    setGraphLoading(true);
    setGraphError(null);
    try {
      setGraph(await adminApi.projectGraph(token, tenantId));
    } catch (err) {
      setGraphError(
        err instanceof Error ? err.message : "Failed to load graph.",
      );
    } finally {
      setGraphLoading(false);
    }
  }

  async function deleteMemory(id: string) {
    if (!token) return;
    try {
      await adminApi.deleteMemoryWrite(token, tenantId, id);
      memories.reload();
    } catch (err) {
      if (err instanceof AdminApiError) alert(err.message);
    }
  }

  // Destructive wipe -- gated on the operator re-typing the tenant_id.
  const [confirmValue, setConfirmValue] = useState("");
  const [wiping, setWiping] = useState(false);

  async function wipe() {
    if (!token || confirmValue !== tenantId) return;
    setWiping(true);
    try {
      await adminApi.wipeProject(token, tenantId);
      router.push("/admin/projects");
    } catch (err) {
      setWiping(false);
      if (err instanceof AdminApiError) alert(err.message);
    }
  }

  return (
    <div>
      <PageHeading
        title={project?.name ?? tenantId}
        subtitle={
          project ? `Owned by ${project.owner_email}` : "Project detail"
        }
      />
      <div className="mb-3 text-sm">
        <Link
          href="/admin/projects"
          className="text-muted-foreground hover:underline"
        >
          ← All projects
        </Link>
      </div>

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="Tenant"
          value={<span className="font-mono text-sm">{tenantId}</span>}
        />
        <StatCard label="Graph nodes" value={project?.node_count ?? "—"} />
        <StatCard label="Graph edges" value={project?.edge_count ?? "—"} />
        <StatCard
          label="Last activity"
          value={
            <span className="text-sm">
              {formatDate(project?.last_activity_at ?? null)}
            </span>
          }
        />
      </div>

      {/* Sources: which agents wrote into this graph, and how much. */}
      <Panel title="Sources (who wrote what)" className="mb-8">
        {sources.loading ? (
          <LoadingRow />
        ) : sources.error ? (
          <ErrorRow message={sources.error} />
        ) : !sources.data || sources.data.length === 0 ? (
          <EmptyRow>No writes recorded for this project yet.</EmptyRow>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground uppercase">
              <tr className="border-b border-border">
                <th className="px-4 py-2 font-medium">Source</th>
                <th className="px-4 py-2 text-right font-medium">Writes</th>
                <th className="px-4 py-2 text-right font-medium">Entities</th>
                <th className="px-4 py-2 text-right font-medium">Relations</th>
                <th className="px-4 py-2 font-medium">Last active</th>
              </tr>
            </thead>
            <tbody>
              {sources.data.map((s) => (
                <tr
                  key={s.source}
                  className="border-b border-border/50 last:border-0"
                >
                  <td className="px-4 py-2 font-mono text-xs">{s.source}</td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {s.write_count}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {s.entities}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {s.relations}
                  </td>
                  <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">
                    {formatDate(s.last_activity_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {/* Raw memory writes: original content vs. what extraction produced. */}
      <Panel title="Recent memory writes" className="mb-8">
        {memories.loading ? (
          <LoadingRow />
        ) : memories.error ? (
          <ErrorRow message={memories.error} />
        ) : !memories.data || memories.data.length === 0 ? (
          <EmptyRow>No memory writes recorded for this project.</EmptyRow>
        ) : (
          <ul className="divide-y divide-border">
            {memories.data.map((m) => (
              <li key={m.id} className="px-4 py-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="rounded bg-muted px-1.5 py-0.5 font-mono">
                        {m.source}
                      </span>
                      <span>{formatDate(m.created_at)}</span>
                      <span>
                        → {m.extracted_entity_count} entities,{" "}
                        {m.extracted_relation_count} relations
                      </span>
                    </div>
                    <p className="text-sm break-words whitespace-pre-wrap">
                      {m.raw_content}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="shrink-0 text-muted-foreground"
                    onClick={() => deleteMemory(m.id)}
                  >
                    Delete log
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
        <p className="border-t border-border px-4 py-2 text-xs text-muted-foreground">
          Deleting a log entry removes only this audit record — it does not
          un-write the graph.
        </p>
      </Panel>

      {/* Live graph (loaded on demand) + entity links into claim history. */}
      <Panel title="Live graph" className="mb-8">
        <div className="p-4">
          {graph ? (
            <>
              <MemoryGraph
                entities={graph.entities}
                relations={graph.relations}
                highlightedIds={null}
              />
              <div className="mt-4">
                <div className="mb-2 text-xs font-medium text-muted-foreground uppercase">
                  Entities — click for full claim history
                </div>
                <div className="flex flex-wrap gap-2">
                  {graph.entities.map((e) => (
                    <Link
                      key={e.id}
                      href={`/admin/projects/${tenantId}/entities/${e.id}`}
                      className="rounded-lg border border-border px-2 py-1 text-xs hover:bg-muted"
                    >
                      {e.name}
                      <span className="ml-1 text-muted-foreground">
                        {e.entity_type}
                      </span>
                    </Link>
                  ))}
                </div>
              </div>
            </>
          ) : graphError ? (
            <ErrorRow message={graphError} />
          ) : (
            <Button
              variant="outline"
              onClick={loadGraph}
              disabled={graphLoading}
            >
              {graphLoading ? "Loading graph…" : "Load live graph"}
            </Button>
          )}
        </div>
      </Panel>

      {/* Destructive controls. */}
      <Panel title="Danger zone" className="border-destructive/40">
        <div className="p-4">
          <p className="mb-3 text-sm text-muted-foreground">
            Permanently wipe this project: its entire FalkorDB graph and all
            Postgres rows (project, API keys, agents, usage, audit log). This
            cannot be undone. Type the tenant id{" "}
            <code className="font-mono">{tenantId}</code> to confirm.
          </p>
          <div className="flex items-center gap-2">
            <Input
              value={confirmValue}
              onChange={(e) => setConfirmValue(e.target.value)}
              placeholder={tenantId}
              className="max-w-xs"
            />
            <Button
              variant="destructive"
              disabled={confirmValue !== tenantId || wiping}
              onClick={wipe}
            >
              {wiping ? "Wiping…" : "Wipe project"}
            </Button>
          </div>
        </div>
      </Panel>
    </div>
  );
}
