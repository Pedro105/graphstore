import Link from "next/link";
import { ExternalLink, Code2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardTitle } from "@/components/ui/card";
import { DemoGraph } from "@/components/landing/demo-graph";
import { SiteFooter } from "@/components/landing/site-footer";
import { SiteHeader } from "@/components/landing/site-header";
import { DOCS_URL } from "@/lib/links";

const SKILLS = [
  {
    title: "Reified Claim Schema",
    description:
      "Facts stored as first-class :Claim nodes with provenance, validity windows, and conflict state — not inlined edge properties.",
  },
  {
    title: "Entity Resolution",
    description:
      "Embedding similarity + property matching merges 'Pedro Costa' and 'P. Costa' onto one shared entity across independent writes.",
  },
  {
    title: "Conflict Adjudication",
    description:
      "When agents contradict each other, claims enter a disputed state for explicit resolution rather than silent overwrites.",
  },
  {
    title: "Hybrid GraphRAG Recall",
    description:
      "Vector seed retrieval followed by graph traversal surfaces connected context that pure similarity search misses.",
  },
  {
    title: "Eval Harness",
    description:
      "Ground-truth dataset with entity presence, property value, and relation value checks — prevents silent regressions.",
  },
  {
    title: "MCP Tools",
    description:
      "Claude Code/Desktop integration via a standalone uvx-installable MCP server exposing remember/recall.",
  },
];

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main className="flex-1">
        {/* Hero */}
        <section className="mx-auto max-w-4xl px-6 py-20 text-center">
          <span className="inline-flex items-center gap-2 rounded border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
            <span className="size-1.5 rounded-full bg-amber-500" />
            Research project — not a live product
          </span>
          <h1 className="mt-6 text-5xl font-light leading-tight tracking-tight text-foreground lg:text-6xl">
            GraphRAG Knowledge Layer
            <br />
            <span className="italic">for Multi-Writer Agents</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground">
            A memory system where multiple agents write structured knowledge to
            a shared graph — with entity resolution, conflict adjudication, and
            provenance on every fact. Not chatbot memory; workflow-shaped memory.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button
              size="lg"
              variant="outline"
              render={
                <a
                  href="https://github.com/Pedro105/graphstore"
                  target="_blank"
                  rel="noopener noreferrer"
                />
              }
            >
              <Code2 className="mr-2 size-4" />
              View source
            </Button>
            <Button
              size="lg"
              variant="outline"
              render={
                <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" />
              }
            >
              <ExternalLink className="mr-2 size-4" />
              Documentation
            </Button>
            <Button size="lg" render={<Link href="/dashboard/memories" />}>
              Try the demo UI
            </Button>
          </div>
          <p className="mt-4 text-sm text-muted-foreground">
            The hosted backend may be offline — see README for local setup.
          </p>
        </section>

        {/* Graph demo */}
        <section className="mx-auto max-w-5xl px-6 pb-16">
          <DemoGraph />
          <p className="mt-4 text-center text-sm text-muted-foreground">
            Example graph: multiple agents (CRM, Support, Product, Account)
            writing about a shared customer, automatically resolved onto unified
            entities.
          </p>
        </section>

        {/* Skills / capabilities */}
        <section className="border-t border-border">
          <div className="mx-auto max-w-5xl px-6 py-16">
            <h2 className="mb-10 text-center text-2xl font-semibold tracking-tight text-foreground">
              Technical Capabilities
            </h2>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {SKILLS.map((skill) => (
                <Card key={skill.title}>
                  <CardContent className="py-5">
                    <CardTitle className="text-base text-foreground">
                      {skill.title}
                    </CardTitle>
                    <CardDescription className="mt-2 leading-relaxed">
                      {skill.description}
                    </CardDescription>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* Architecture pointer */}
        <section className="border-t border-border">
          <div className="mx-auto max-w-3xl px-6 py-16 text-center">
            <h2 className="text-xl font-semibold text-foreground">
              Architecture
            </h2>
            <p className="mt-3 text-muted-foreground leading-relaxed">
              FastAPI backend, FalkorDB graph store with native vector index,
              Postgres for auth/billing metadata, LLM-powered extraction
              (Claude Haiku). Claims are reified as <code>:Claim</code> nodes
              linked to subject/object entities via <code>:SUBJECT</code> /{" "}
              <code>:OBJECT</code> edges — the predicate is a node property,
              not an edge type.
            </p>
            <div className="mt-6 flex items-center justify-center gap-3">
              <Button
                variant="outline"
                render={
                  <a
                    href="https://github.com/Pedro105/graphstore/blob/main/docs/architecture.md"
                    target="_blank"
                    rel="noopener noreferrer"
                  />
                }
              >
                Architecture doc
              </Button>
              <Button
                variant="outline"
                render={
                  <a
                    href="https://github.com/Pedro105/graphstore/tree/main/docs/decisions"
                    target="_blank"
                    rel="noopener noreferrer"
                  />
                }
              >
                ADRs
              </Button>
            </div>
          </div>
        </section>

        {/* Status */}
        <section className="border-t border-border">
          <div className="mx-auto max-w-3xl px-6 py-16 text-center">
            <h2 className="text-xl font-semibold text-foreground">
              Project Status
            </h2>
            <p className="mt-3 text-muted-foreground leading-relaxed">
              Personal research / portfolio project. Business exploration
              paused. The hosted Fly.io backend may be offline — run locally
              with Docker (FalkorDB) + <code>uv</code> to explore.
            </p>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
