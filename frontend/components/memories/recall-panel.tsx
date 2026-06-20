"use client";

import { useState, type FormEvent } from "react";
import { Info } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import type { RecallResult, RetrievalStats } from "@/lib/api";

interface RecallPanelProps {
  onRecall: (query: string) => Promise<void>;
  onClear: () => void;
  recalling: boolean;
  error: string | null;
  result: RecallResult | null;
}

const DEFAULT_QUERY = "What price and delivery timing should we give Acme Corp for Product Y?";

// Total/synthesis latency: seconds (1 d.p.) once we cross a second, else ms.
function formatMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

const QUERY_CLASS_LABELS: Record<string, string> = {
  relational: "Relational",
  single_hop: "Single hop",
  exact_lookup: "Exact lookup",
  manual: "Manual",
};

function formatQueryClass(queryClass: string): string {
  return (
    QUERY_CLASS_LABELS[queryClass] ??
    queryClass.replace(/_/g, " ").replace(/^\w/, (char) => char.toUpperCase())
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono tabular-nums">{value}</span>
    </div>
  );
}

function StatsPopover({ stats }: { stats: RetrievalStats }) {
  return (
    <Popover>
      <PopoverTrigger
        aria-label="Show retrieval stats"
        className="inline-flex shrink-0 items-center text-muted-foreground transition-colors hover:text-foreground"
      >
        <Info size={14} />
      </PopoverTrigger>
      <PopoverContent>
        <p className="font-medium">Recalled in {formatMs(stats.total_ms)}</p>
        <Separator className="my-2" />
        <div className="flex flex-col gap-1">
          <StatRow label="Seeded" value={`${stats.seeds_found} entities`} />
          <StatRow
            label="Traversed"
            value={`${stats.nodes_traversed} nodes · depth ${stats.depth_reached}`}
          />
          <StatRow label="Relations" value={`${stats.relations_found} edges`} />
          <StatRow label="Query type" value={formatQueryClass(stats.query_class)} />
          {stats.synthesis_ms !== null && (
            <StatRow label="Synthesis" value={formatMs(stats.synthesis_ms)} />
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

export function RecallPanel({ onRecall, onClear, recalling, error, result }: RecallPanelProps) {
  const [query, setQuery] = useState(DEFAULT_QUERY);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    await onRecall(query.trim());
  }

  const contributingSources = result
    ? Array.from(new Set(result.entities.map((entity) => entity.provenance.source)))
    : [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recall</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Ask a question across the graph"
          />
          <Button type="submit" disabled={recalling || !query.trim()}>
            {recalling ? "Recalling..." : "Recall"}
          </Button>
          {result && (
            <Button type="button" variant="outline" onClick={onClear}>
              Clear
            </Button>
          )}
        </form>
        {error && <p className="text-sm text-destructive">{error}</p>}
        {result && (
          <div className="flex flex-col gap-3 rounded-xl border border-border bg-muted/30 p-4">
            <div className="flex items-center gap-1.5">
              <p className="text-sm text-muted-foreground">
                {contributingSources.length > 1
                  ? `Answered using facts from ${contributingSources.length} sources: ${contributingSources.join(", ")}`
                  : contributingSources.length === 1
                    ? `Answered using facts from "${contributingSources[0]}"`
                    : "No matching facts found."}
              </p>
              {result.stats && <StatsPopover stats={result.stats} />}
            </div>
            <div>
              <p className="mb-1.5 font-mono text-xs text-muted-foreground">
                entities ({result.entities.length})
              </p>
              <ul className="flex flex-wrap gap-1.5">
                {result.entities.map((entity) => (
                  <li key={entity.id}>
                    <Badge variant="secondary">{entity.name}</Badge>
                  </li>
                ))}
              </ul>
            </div>
            {result.relations.length > 0 && (
              <div>
                <p className="mb-1.5 font-mono text-xs text-muted-foreground">
                  relations ({result.relations.length})
                </p>
                <ul className="flex flex-col gap-1 font-mono text-xs text-muted-foreground">
                  {result.relations.map((relation) => {
                    const sourceName =
                      result.entities.find((entity) => entity.id === relation.source_entity_id)
                        ?.name ?? relation.source_entity_id;
                    const targetName =
                      result.entities.find((entity) => entity.id === relation.target_entity_id)
                        ?.name ?? relation.target_entity_id;
                    return (
                      <li key={relation.id}>
                        {sourceName} <span className="text-foreground">{relation.relation_type}</span>{" "}
                        {targetName}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
