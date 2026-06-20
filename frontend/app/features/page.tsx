import Link from "next/link";
import {
  Database,
  GitMerge,
  Globe,
  Key,
  Network,
  Search,
  Shield,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardTitle } from "@/components/ui/card";
import { SiteFooter } from "@/components/landing/site-footer";
import { SiteHeader } from "@/components/landing/site-header";

const FEATURES = [
  {
    icon: Network,
    title: "GraphRAG Memory",
    description:
      "Hybrid vector and graph retrieval returns connected, structured answers — not just semantically similar chunks. Queries traverse the graph from relevant seeds, surfacing related entities and relations your agents actually need.",
    badge: "Core",
  },
  {
    icon: GitMerge,
    title: "Entity Resolution",
    description:
      "When two agents mention the same customer, product, or supplier, ContextStore automatically merges them onto one shared entity using vector-similarity matching. No duplicate records. No conflicting state.",
    badge: "Core",
  },
  {
    icon: Zap,
    title: "Multi-Agent Concurrent Writes",
    description:
      "Multiple agents, jobs, and AI features write into the same graph simultaneously. Relation deduplication at write time via MERGE semantics means repeated facts increment a support count rather than creating noise.",
    badge: "Core",
  },
  {
    icon: Shield,
    title: "Tenant Isolation",
    description:
      "Structural isolation — not filtering. Each tenant gets a dedicated FalkorDB graph, so your data is separated at the storage layer. Vector search results are never mixed across tenants.",
    badge: "Security",
  },
  {
    icon: Database,
    title: "Provenance Tracking",
    description:
      "Every entity and relation is tagged with the memory it came from, the agent that wrote it, and a timestamp. You always know where a fact came from, enabling audit trails and conflict resolution.",
    badge: "Core",
  },
  {
    icon: Globe,
    title: "REST API",
    description:
      "Two simple endpoints — remember() and recall() — work with any agent framework or programming language. If you can make an HTTP request, you can use ContextStore.",
    badge: "API",
  },
  {
    icon: Key,
    title: "MCP Integration",
    description:
      "Native Claude Code and Claude Desktop integration out of the box. The MCP server exposes remember and recall as first-class tools, so your Claude agents get persistent memory with zero glue code.",
    badge: "Integrations",
  },
  {
    icon: Search,
    title: "LLM-Powered Extraction",
    description:
      "Natural language in, structured knowledge out. Claude Haiku extracts entities and relations from any text your agents produce — no schema definition, no structured output templates required.",
    badge: "Core",
  },
];

const BADGE_COLORS: Record<string, string> = {
  Core: "bg-foreground/8 text-foreground/70",
  Security: "bg-emerald-50 text-emerald-700",
  API: "bg-indigo-50 text-indigo-700",
  Integrations: "bg-amber-50 text-amber-700",
};

export default function FeaturesPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main className="flex-1">
        {/* Hero */}
        <section className="mx-auto max-w-4xl px-6 py-24 text-center">
          <span className="rounded border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
            Memory infrastructure
          </span>
          <h1 className="mt-5 text-5xl font-semibold tracking-tight text-foreground">
            Built for production AI workflows
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-muted-foreground leading-relaxed">
            ContextStore isn&apos;t a chatbot memory layer. It&apos;s
            workflow-shaped memory — designed for multi-agent systems where
            dozens of agents write and read concurrently, with full provenance
            on every fact.
          </p>
          <div className="mt-8 flex items-center justify-center gap-3">
            <Button size="lg" render={<Link href="/dashboard" />}>
              Start building
            </Button>
            <Button
              size="lg"
              variant="outline"
              render={<Link href="/api-reference" />}
            >
              View API reference
            </Button>
          </div>
        </section>

        {/* Features grid */}
        <section className="border-t border-border">
          <div className="mx-auto max-w-5xl px-6 py-20">
            <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-2">
              {FEATURES.map((feature) => {
                const Icon = feature.icon;
                return (
                  <Card key={feature.title}>
                    <CardContent className="flex flex-col gap-3 py-5">
                      <div className="flex items-start justify-between">
                        <div className="rounded border border-border bg-muted p-2">
                          <Icon className="size-4 text-foreground/70" />
                        </div>
                        <span
                          className={`rounded px-2 py-0.5 text-xs font-medium ${BADGE_COLORS[feature.badge]}`}
                        >
                          {feature.badge}
                        </span>
                      </div>
                      <CardTitle className="text-foreground">
                        {feature.title}
                      </CardTitle>
                      <CardDescription className="leading-relaxed">
                        {feature.description}
                      </CardDescription>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>
        </section>

        {/* Technical highlight */}
        <section className="border-t border-border">
          <div className="mx-auto max-w-5xl px-6 py-20">
            <div className="grid items-center gap-12 md:grid-cols-2">
              <div>
                <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                  The graph is the source of truth
                </h2>
                <p className="mt-3 text-muted-foreground leading-relaxed">
                  Entities resolve across every write. When a pricing agent
                  mentions &quot;Acme Corp&quot; and a CRM agent has already
                  written about it, they land on the same node — and the
                  pricing agent&apos;s facts attach there automatically.
                </p>
                <ul className="mt-6 space-y-3">
                  {[
                    "FalkorDB graph + vector index, one query",
                    "Cosine similarity for entity matching",
                    "MERGE deduplication for relations",
                    "One hop traversal from entity seeds",
                  ].map((point) => (
                    <li
                      key={point}
                      className="flex items-start gap-2.5 text-sm text-muted-foreground"
                    >
                      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-foreground/35" />
                      {point}
                    </li>
                  ))}
                </ul>
              </div>
              <Card>
                <CardContent className="py-5 font-mono text-xs">
                  <div className="mb-3 text-muted-foreground">
                    # remember — write structured knowledge
                  </div>
                  <div className="space-y-1.5 text-foreground/80">
                    <div>
                      <span className="text-indigo-600">POST</span>{" "}
                      /v1/memories
                    </div>
                    <div className="pl-4 text-muted-foreground">
                      {"{"}&quot;text&quot;: &quot;Acme Corp expects 500 units
                      of Product Y&quot;,
                    </div>
                    <div className="pl-4 text-muted-foreground">
                      &quot;scope&quot;: {"{"}&quot;tenant_id&quot;:
                      &quot;demo&quot;, &quot;agent_id&quot;:
                      &quot;crm-agent&quot;{"}"}{"}"}{" "}
                    </div>
                  </div>
                  <div className="mt-4 mb-3 text-muted-foreground">
                    # recall — query the graph
                  </div>
                  <div className="space-y-1.5 text-foreground/80">
                    <div>
                      <span className="text-indigo-600">POST</span> /v1/recall
                    </div>
                    <div className="pl-4 text-muted-foreground">
                      {"{"}&quot;query&quot;: &quot;What does Acme Corp
                      need?&quot;,
                    </div>
                    <div className="pl-4 text-muted-foreground">
                      &quot;scope&quot;: {"{"}&quot;tenant_id&quot;:
                      &quot;demo&quot;{"}"}{"}"}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="border-t border-border">
          <div className="mx-auto max-w-2xl px-6 py-20 text-center">
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">
              Ready to give your agents memory?
            </h2>
            <p className="mt-3 text-muted-foreground">
              Start on the free tier. No infrastructure to manage.
            </p>
            <div className="mt-7 flex items-center justify-center gap-3">
              <Button size="lg" render={<Link href="/dashboard" />}>
                Get started free
              </Button>
              <Button
                size="lg"
                variant="outline"
                render={<Link href="/pricing" />}
              >
                See pricing
              </Button>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
