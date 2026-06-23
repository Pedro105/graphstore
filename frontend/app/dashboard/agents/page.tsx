"use client";

import { useMemo, useState } from "react";
import { Bot, PlusIcon, Radar, Trash2Icon } from "lucide-react";

import {
  AgentDialog,
  type AgentFormValues,
} from "@/components/agents/agent-dialog";
import { AgentSetupGuide } from "@/components/agents/agent-setup-guide";
import { AgentLeaderboard } from "@/components/dashboard/agent-leaderboard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { colorForType } from "@/lib/entity-colors";
import { compactNumber, relativeTime } from "@/lib/format";
import { useAgents } from "@/lib/hooks/use-agents";
import { useSources } from "@/lib/hooks/use-observability";
import type { SourceActivity } from "@/lib/api";

function ContributionStats({ source }: { source: SourceActivity }) {
  return (
    <div className="mt-1 flex flex-col gap-1">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
        <span>
          <span className="font-medium text-foreground">
            {compactNumber(source.write_count)}
          </span>{" "}
          writes
        </span>
        <span>
          <span className="font-medium text-foreground">
            {compactNumber(source.entities)}
          </span>{" "}
          entities
        </span>
        <span>
          <span className="font-medium text-foreground">
            {compactNumber(source.relations)}
          </span>{" "}
          relations
        </span>
      </div>
      <span className="text-xs text-muted-foreground/80">
        last wrote {relativeTime(source.last_activity_at)}
      </span>
    </div>
  );
}

export default function AgentsPage() {
  const { agents, loading, error, create, remove, reload } = useAgents();
  const { sources, loading: sourcesLoading } = useSources();
  const [dialogOpen, setDialogOpen] = useState(false);
  // After a successful create, show the setup guide for the new agent.
  const [guideFor, setGuideFor] = useState<string | null>(null);

  async function handleSubmit(values: AgentFormValues) {
    const name = values.name.trim();
    await create({ name, description: values.description.trim() || null });
    setGuideFor(name);
  }

  const sourceByName = useMemo(() => {
    const map = new Map<string, SourceActivity>();
    for (const source of sources) map.set(source.source, source);
    return map;
  }, [sources]);

  // Sources that have written but were never registered as agents — a real,
  // useful signal in a multi-agent setup (a stray source name, a job nobody
  // registered). Surfaced so they're visible, not silently dropped.
  const unregistered = useMemo(() => {
    const registered = new Set(agents.map((a) => a.name));
    return sources.filter((s) => !registered.has(s.source));
  }, [agents, sources]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Agents</h1>
          <p className="text-muted-foreground">
            The named agents that write into shared memory — and what each has
            contributed.
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <PlusIcon />
          New agent
        </Button>
      </div>

      {error ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <p className="max-w-sm text-sm text-destructive">{error}</p>
            <Button size="sm" variant="outline" onClick={() => void reload()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : loading && agents.length === 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="space-y-3">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-3 w-40" />
                <Skeleton className="h-3 w-48" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : agents.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center">
            <Bot className="size-6 text-muted-foreground" />
            <p className="font-medium">No agents yet</p>
            <p className="max-w-sm text-sm text-muted-foreground">
              Register the agents that write into your shared memory graph. Once
              registered, each agent&apos;s write activity and graph
              contribution show up here.
            </p>
            <Button
              size="sm"
              className="mt-2"
              onClick={() => setDialogOpen(true)}
            >
              <PlusIcon /> Register an agent
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => {
            const source = sourceByName.get(agent.name);
            const color = colorForType(agent.name);
            return (
              <Card key={agent.id}>
                <CardContent className="flex flex-col gap-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex min-w-0 items-center gap-2">
                      <span
                        aria-hidden
                        className="flex size-7 shrink-0 items-center justify-center rounded-full"
                        style={{ backgroundColor: `${color}1a`, color }}
                      >
                        <Bot className="size-3.5" />
                      </span>
                      <span className="truncate font-medium">{agent.name}</span>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => remove(agent.id)}
                    >
                      <Trash2Icon />
                    </Button>
                  </div>
                  {agent.description && (
                    <p className="text-sm text-muted-foreground">
                      {agent.description}
                    </p>
                  )}
                  {sourcesLoading && !source ? (
                    <Skeleton className="mt-1 h-3 w-40" />
                  ) : source ? (
                    <ContributionStats source={source} />
                  ) : (
                    <p className="mt-1 text-xs text-muted-foreground/80">
                      No writes yet — this agent hasn&apos;t written to the
                      graph.
                    </p>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {unregistered.length > 0 ? (
        <section className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
          <div className="mb-1">
            <h2 className="font-heading text-base font-semibold tracking-tight">
              Unregistered sources
            </h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              These sources have written to the graph but aren&apos;t in your
              agent registry. Register them to track them as agents.
            </p>
          </div>
          <AgentLeaderboard sources={unregistered} loading={false} />
        </section>
      ) : null}

      {/* Honest note: per-agent write activity is real (from memory_writes), but
          recalls aren't attributed to a source, so per-agent read counts aren't
          available from the current data. */}
      {agents.length > 0 ? (
        <p className="text-xs text-muted-foreground">
          Write activity is attributed per agent via the{" "}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">
            source
          </code>{" "}
          field. Recalls aren&apos;t attributed to a source, so per-agent read
          counts aren&apos;t tracked yet.
        </p>
      ) : null}

      {/* Scaffold, not fake data: loop/behavioural analysis needs signals the
          backend doesn't capture yet. Stated plainly rather than mocked. */}
      <section className="rounded-xl border border-dashed border-border bg-muted/30 p-5">
        <div className="flex items-start gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
            <Radar className="size-5" />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-heading text-base font-semibold tracking-tight">
                Loop detection & behavioral analysis
              </h2>
              <span className="inline-flex items-center rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                Coming soon
              </span>
            </div>
            <p className="mt-1 max-w-xl text-sm text-muted-foreground">
              Surfacing runaway write loops, repetitive no-op recalls, and
              anomalous agent behavior needs per-call tracing the store
              doesn&apos;t capture yet. When it does, this is where you&apos;ll
              see flagged patterns — not estimates or mocked numbers.
            </p>
          </div>
        </div>
      </section>

      <AgentDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSubmit={handleSubmit}
      />
      <AgentSetupGuide
        agentName={guideFor}
        open={guideFor !== null}
        onOpenChange={(open) => (!open ? setGuideFor(null) : undefined)}
      />
    </div>
  );
}
