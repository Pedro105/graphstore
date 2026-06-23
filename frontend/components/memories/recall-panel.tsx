"use client";

import { useState, type FormEvent } from "react";
import { Check, ChevronDown, Info, Sparkles, History } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import { RelationshipTrace } from "@/components/memories/relationship-trace";
import { cn } from "@/lib/utils";
import type {
  ClassifierResult,
  RecallResult,
  RetrievalStats,
  SynthesisResult,
} from "@/lib/api";

interface RecallPanelProps {
  onRecall: (query: string, synthesise: boolean) => Promise<void>;
  onClear: () => void;
  recalling: boolean;
  error: string | null;
  result: RecallResult | null;
}

const DEFAULT_QUERY =
  "What price and delivery timing should we give Acme Corp for Product Y?";

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

const MODE_LABELS: Record<string, string> = {
  vector: "vector similarity",
  fulltext: "full-text",
  hybrid: "hybrid search",
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
          <StatRow
            label="Query type"
            value={formatQueryClass(stats.query_class)}
          />
          {stats.synthesis_ms !== null && (
            <StatRow label="Synthesis" value={formatMs(stats.synthesis_ms)} />
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

// One-line explanation of *how* the query was routed — the classifier's
// decision, which the backend captures and the UI surfaces here.
function RoutingExplanation({
  classifier,
  stats,
}: {
  classifier: ClassifierResult | null;
  stats: RetrievalStats;
}) {
  if (classifier) {
    const mode =
      MODE_LABELS[classifier.strategy.retrieval_mode] ??
      classifier.strategy.retrieval_mode;
    const depth = classifier.strategy.traversal_depth;
    const decider = classifier.used_llm ? "LLM classifier" : "heuristic";
    const conf = Math.round(classifier.confidence * 100);
    return (
      <p className="text-xs text-muted-foreground">
        Routed as{" "}
        <span className="font-medium text-foreground">
          {formatQueryClass(classifier.query_class)}
        </span>{" "}
        → {mode}, {depth} hop{depth === 1 ? "" : "s"}
        <span className="text-muted-foreground/70">
          {" "}
          · {decider} {conf}%
        </span>
      </p>
    );
  }
  return (
    <p className="text-xs text-muted-foreground">
      Manual routing → depth {stats.depth_reached}
    </p>
  );
}

const SYNTH_CONFIDENCE_STYLES: Record<string, string> = {
  high: "bg-emerald-50 text-emerald-700",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-orange-50 text-orange-700",
  insufficient_data: "bg-muted text-muted-foreground",
};

// The hero: the direct answer to the question, displayed large and first.
function AnswerHero({ synthesis }: { synthesis: SynthesisResult }) {
  return (
    <div className="rounded-xl border border-data-accent/30 bg-data-accent-soft p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 text-xs font-medium tracking-wide text-data-accent uppercase">
          <Sparkles className="size-3.5" /> Answer
        </span>
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-[10px] font-medium",
            SYNTH_CONFIDENCE_STYLES[synthesis.confidence] ??
              "bg-muted text-muted-foreground",
          )}
        >
          {synthesis.confidence.replace(/_/g, " ")}
        </span>
      </div>
      <p className="text-[15px] leading-relaxed text-foreground">
        {synthesis.answer}
      </p>
      {synthesis.caveat ? (
        <p className="mt-2.5 border-t border-data-accent/20 pt-2.5 text-xs text-muted-foreground">
          {synthesis.caveat}
        </p>
      ) : null}
    </div>
  );
}

function FullGraphContext({ result }: { result: RecallResult }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-border">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
        aria-expanded={open}
      >
        <span>
          Full graph context · {result.entities.length} entities,{" "}
          {result.relations.length} relations
        </span>
        <ChevronDown
          className={cn("size-3.5 transition-transform", open && "rotate-180")}
        />
      </button>
      {open ? (
        <div className="flex flex-col gap-3 border-t border-border px-3 py-3">
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
                    result.entities.find(
                      (entity) => entity.id === relation.source_entity_id,
                    )?.name ?? relation.source_entity_id;
                  const targetName =
                    result.entities.find(
                      (entity) => entity.id === relation.target_entity_id,
                    )?.name ?? relation.target_entity_id;
                  return (
                    <li key={relation.id}>
                      {sourceName}{" "}
                      <span className="text-foreground">
                        {relation.relation_type}
                      </span>{" "}
                      {targetName}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

export function RecallPanel({
  onRecall,
  onClear,
  recalling,
  error,
  result,
}: RecallPanelProps) {
  const [query, setQuery] = useState(DEFAULT_QUERY);
  // Synthesis on by default — the dashboard is human-facing and the answer is
  // the point. Users can switch it off to skip synthesis latency.
  const [synthesise, setSynthesise] = useState(true);
  // Session-scoped query history (most recent first, deduped). Cleared on reload.
  const [history, setHistory] = useState<string[]>([]);

  async function run(q: string) {
    const trimmed = q.trim();
    if (!trimmed) return;
    setHistory((prev) =>
      [trimmed, ...prev.filter((h) => h !== trimmed)].slice(0, 6),
    );
    await onRecall(trimmed, synthesise);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    await run(query);
  }

  const contributingSources = result
    ? Array.from(
        new Set(result.entities.map((entity) => entity.provenance.source)),
      )
    : [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recall</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <form onSubmit={handleSubmit} className="flex flex-col gap-2">
          <div className="flex gap-2">
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
          </div>
          <button
            type="button"
            onClick={() => setSynthesise((v) => !v)}
            className="inline-flex w-fit items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
            aria-pressed={synthesise}
          >
            <span
              className={cn(
                "flex size-3.5 items-center justify-center rounded border",
                synthesise
                  ? "border-data-accent bg-data-accent text-data-accent-foreground"
                  : "border-border",
              )}
            >
              {synthesise ? <Check className="size-2.5" /> : null}
            </span>
            Generate a natural-language answer
          </button>
        </form>

        {history.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <History className="size-3 text-muted-foreground" />
            {history.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => {
                  setQuery(item);
                  void run(item);
                }}
                className="max-w-[14rem] truncate rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                title={item}
              >
                {item}
              </button>
            ))}
          </div>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}

        {result && (
          <div className="flex flex-col gap-3 rounded-xl border border-border bg-muted/30 p-4">
            {/* The direct answer leads when synthesis is present. */}
            {result.synthesis && <AnswerHero synthesis={result.synthesis} />}

            <div className="flex items-start justify-between gap-2">
              <div className="flex flex-col gap-0.5">
                <p className="text-sm text-muted-foreground">
                  {contributingSources.length > 1
                    ? `Answered using facts from ${contributingSources.length} sources: ${contributingSources.join(", ")}`
                    : contributingSources.length === 1
                      ? `Answered using facts from "${contributingSources[0]}"`
                      : "No matching facts found."}
                </p>
                <RoutingExplanation
                  classifier={result.classifier_result}
                  stats={result.stats}
                />
              </div>
              {result.stats && <StatsPopover stats={result.stats} />}
            </div>

            {result.truncated && (
              <p className="text-xs text-amber-700">
                Result truncated — the subgraph hit the entity cap before fully
                expanding.
              </p>
            )}

            {/* The path(s) through the graph that connect the facts behind the
                answer — readable chains, not a raw edge dump. */}
            {result.relations.length > 0 ? (
              <RelationshipTrace
                entities={result.entities}
                relations={result.relations}
                groundedIds={result.synthesis?.grounded_entity_ids ?? []}
              />
            ) : null}

            {result.entities.length > 0 ? (
              <FullGraphContext result={result} />
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
