import Link from "next/link";
import { ArrowRight, BookOpen, Code2, Cpu, Terminal, Zap } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardTitle } from "@/components/ui/card";
import { SiteFooter } from "@/components/landing/site-footer";
import { SiteHeader } from "@/components/landing/site-header";

const QUICK_START_STEPS = [
  {
    step: "01",
    title: "Get an API key",
    description: "Sign up and create your first API key from the dashboard.",
    code: null,
  },
  {
    step: "02",
    title: "Call remember()",
    description:
      "Send any natural language text to the /v1/memories endpoint. ContextStore extracts entities and relations automatically.",
    code: `curl -X POST https://api.contextstore.ai/v1/memories \\
  -H "Authorization: Bearer <your-api-key>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "text": "Acme Corp expects 500 units of Product Y by Q3",
    "scope": { "tenant_id": "your-tenant", "agent_id": "crm-agent" }
  }'`,
  },
  {
    step: "03",
    title: "Query with recall()",
    description:
      "Ask a natural language question. ContextStore traverses the graph and returns structured, connected context.",
    code: `curl -X POST https://api.contextstore.ai/v1/recall \\
  -H "Authorization: Bearer <your-api-key>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "What does Acme Corp need?",
    "scope": { "tenant_id": "your-tenant" }
  }'`,
  },
];

const CONCEPTS = [
  {
    icon: BookOpen,
    title: "Tenants & Scopes",
    description:
      "Understand structural isolation, tenant graphs, and how scope keys filter within a tenant.",
    href: "#tenants",
  },
  {
    icon: Cpu,
    title: "Entity Resolution",
    description:
      "How ContextStore merges the same entity across different agents using vector similarity.",
    href: "#resolution",
  },
  {
    icon: Zap,
    title: "GraphRAG Retrieval",
    description:
      "How recall() finds seeds, traverses the graph, and assembles a RecallResult.",
    href: "#retrieval",
  },
  {
    icon: Code2,
    title: "Provenance",
    description:
      "Every fact is tagged with its source memory, agent, and timestamp. Learn how to use it.",
    href: "#provenance",
  },
];

const SDK_EXAMPLES = {
  python: `from contextstore import ContextStore

cs = ContextStore(api_key="sk-...", tenant_id="your-tenant")

# Write
await cs.remember(
    "Globex quoted $4.20/unit for Product Y",
    agent_id="supplier-agent"
)

# Read
result = await cs.recall("What's the unit cost of Product Y?")
print(result.summary)`,
  mcp: `# ~/.cursor/mcp.json
{
  "mcpServers": {
    "contextstore": {
      "command": "contextstore-mcp",
      "env": {
        "CONTEXTSTORE_API_KEY": "sk-...",
        "CONTEXTSTORE_BASE_URL": "https://api.contextstore.ai"
      }
    }
  }
}`,
};

export default function DocsPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main className="flex-1">
        {/* Hero */}
        <section className="border-b border-border">
          <div className="mx-auto max-w-5xl px-6 py-16">
            <div className="flex items-start gap-8 md:gap-16">
              <div className="flex-1">
                <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Documentation
                </span>
                <h1 className="mt-2 text-4xl font-semibold tracking-tight text-foreground">
                  Get started with ContextStore
                </h1>
                <p className="mt-4 text-muted-foreground leading-relaxed max-w-xl">
                  Everything you need to add persistent, queryable memory to
                  your AI agents. Start with the quick start below, then
                  explore the API reference.
                </p>
                <div className="mt-6 flex items-center gap-3">
                  <Button size="sm" render={<Link href="/api-reference" />}>
                    API Reference
                    <ArrowRight className="size-3.5" />
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    render={<Link href="/dashboard" />}
                  >
                    Open dashboard
                  </Button>
                </div>
              </div>
              <div className="hidden lg:block">
                <Card className="w-72">
                  <CardContent className="py-4">
                    <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                      Quick links
                    </p>
                    <ul className="space-y-2">
                      {[
                        { label: "Quick start", href: "#quick-start" },
                        { label: "Concepts", href: "#concepts" },
                        { label: "Python SDK", href: "#sdks" },
                        { label: "MCP integration", href: "#mcp" },
                        { label: "API reference", href: "/api-reference" },
                      ].map((link) => (
                        <li key={link.label}>
                          <Link
                            href={link.href}
                            className="flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
                          >
                            <ArrowRight className="size-3 shrink-0" />
                            {link.label}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        </section>

        {/* Quick start */}
        <section id="quick-start" className="border-b border-border">
          <div className="mx-auto max-w-5xl px-6 py-16">
            <h2 className="mb-8 text-2xl font-semibold tracking-tight text-foreground">
              Quick start
            </h2>
            <div className="space-y-8">
              {QUICK_START_STEPS.map((step) => (
                <div key={step.step} className="flex gap-6">
                  <div className="flex flex-col items-center">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded border border-border bg-card text-xs font-medium text-muted-foreground">
                      {step.step}
                    </span>
                    <div className="mt-2 flex-1 border-l border-border/50" />
                  </div>
                  <div className="flex-1 pb-8">
                    <h3 className="font-semibold text-foreground">
                      {step.title}
                    </h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {step.description}
                    </p>
                    {step.code && (
                      <Card className="mt-4">
                        <CardContent className="py-4">
                          <pre className="overflow-x-auto font-mono text-xs text-foreground/80 leading-relaxed whitespace-pre">
                            {step.code}
                          </pre>
                        </CardContent>
                      </Card>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Concepts */}
        <section id="concepts" className="border-b border-border">
          <div className="mx-auto max-w-5xl px-6 py-16">
            <h2 className="mb-8 text-2xl font-semibold tracking-tight text-foreground">
              Core concepts
            </h2>
            <div className="grid gap-4 md:grid-cols-2">
              {CONCEPTS.map((concept) => {
                const Icon = concept.icon;
                return (
                  <Link key={concept.title} href={concept.href}>
                    <Card className="transition-colors hover:border-foreground/20">
                      <CardContent className="flex gap-4 py-5">
                        <div className="rounded border border-border bg-muted p-2 h-fit">
                          <Icon className="size-4 text-foreground/70" />
                        </div>
                        <div>
                          <CardTitle className="text-foreground">
                            {concept.title}
                          </CardTitle>
                          <CardDescription className="mt-1">
                            {concept.description}
                          </CardDescription>
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                );
              })}
            </div>
          </div>
        </section>

        {/* SDKs */}
        <section id="sdks" className="border-b border-border">
          <div className="mx-auto max-w-5xl px-6 py-16">
            <h2 className="mb-2 text-2xl font-semibold tracking-tight text-foreground">
              Python SDK
            </h2>
            <p className="mb-8 text-muted-foreground">
              Install with pip and start writing in a few lines.
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Card className="mb-3">
                  <CardContent className="py-3">
                    <pre className="font-mono text-xs text-foreground/80">
                      pip install contextstore
                    </pre>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="py-4">
                    <pre className="overflow-x-auto font-mono text-xs text-foreground/80 leading-relaxed whitespace-pre">
                      {SDK_EXAMPLES.python}
                    </pre>
                  </CardContent>
                </Card>
              </div>
              <div>
                <h3 id="mcp" className="mb-3 font-semibold text-foreground flex items-center gap-2">
                  <Terminal className="size-4" />
                  MCP Integration
                </h3>
                <p className="mb-4 text-sm text-muted-foreground">
                  Register ContextStore as an MCP server in Claude Code or
                  Claude Desktop. Your Claude agents get remember and recall
                  as native tools.
                </p>
                <Card>
                  <CardContent className="py-4">
                    <pre className="overflow-x-auto font-mono text-xs text-foreground/80 leading-relaxed whitespace-pre">
                      {SDK_EXAMPLES.mcp}
                    </pre>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section>
          <div className="mx-auto max-w-3xl px-6 py-16 text-center">
            <h2 className="text-xl font-semibold text-foreground">
              Ready to go deeper?
            </h2>
            <p className="mt-2 text-muted-foreground">
              The full API reference documents every endpoint, parameter, and
              response shape.
            </p>
            <Button
              size="lg"
              variant="outline"
              className="mt-6"
              render={<Link href="/api-reference" />}
            >
              View API reference
              <ArrowRight className="size-4" />
            </Button>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
