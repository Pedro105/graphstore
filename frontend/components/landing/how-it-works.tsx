import { Card, CardContent } from "@/components/ui/card";

const WRITE_CODE = `import contextstore

cs = contextstore.Client(
    api_key="sk-...",
    tenant_id="saas_platform"
)

await cs.remember(
    "Meridian Corp (850 seats) is up for renewal "
    "in 23 days. Contact: Sofia Reyes, VP Eng.",
    agent_id="crm-agent"
)`;

const RECALL_CODE = `result = await cs.recall(
    "What's the status of Meridian Corp?",
)

# result.entities
# → Meridian Corp (Organization)
# → Sofia Reyes (Person)
# → Rate Limit Issue (Issue)
# → $42k Expansion (Opportunity)
# → v3.4.0 Release (Release)

# result.relations
# → Rate Limit Issue AFFECTS Data Export API
# → v3.4.0 Release FIXES Rate Limit Issue
# (from 4 agent writes, full provenance)`;

const EXTRACTED_ENTITIES = [
  { name: "Meridian Corp", type: "Organization", color: "#6366f1" },
  { name: "Sofia Reyes", type: "Person", color: "#f59e0b" },
  { name: "Renewal June 30", type: "Date", color: "#3b82f6" },
  { name: "850 seats", type: "Metric", color: "#14b8a6" },
];

const EXTRACTED_RELATIONS = [
  { from: "Sofia Reyes", rel: "WORKS_AT", to: "Meridian Corp" },
  { from: "Meridian Corp", rel: "RENEWS_ON", to: "Renewal June 30" },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="bg-background">
      <div className="mx-auto max-w-6xl px-6 py-24">
        {/* Section header */}
        <div className="mb-20 max-w-2xl">
          <h2 className="text-4xl font-light leading-tight text-foreground lg:text-5xl">
            From natural language
            <br />
            <span className="italic">to queryable knowledge</span>
          </h2>
          <p className="mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
            Four steps turn raw text from any agent into structured, connected
            knowledge — immediately available to every other agent in your
            tenant.
          </p>
        </div>

        {/* Step 01 — Write */}
        <div className="mb-28 grid items-center gap-12 lg:grid-cols-2">
          <div className="relative">
            <span
              aria-hidden="true"
              className="pointer-events-none absolute -left-1 -top-8 select-none font-heading text-[9rem] font-light leading-none text-foreground/6 lg:text-[11rem]"
            >
              01
            </span>
            <div className="relative">
              <h3 className="text-3xl font-medium text-foreground lg:text-4xl">
                Write in plain language
              </h3>
              <p className="mt-4 leading-relaxed text-muted-foreground">
                Any agent sends a sentence of natural language to{" "}
                <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-sm text-foreground">
                  remember()
                </code>
                . One HTTP call. No schema required. Works with Python,
                TypeScript, curl — anything that can make an HTTP request.
              </p>
              <ul className="mt-5 space-y-2.5">
                {[
                  "Any programming language or framework",
                  "No structured output templates required",
                  "Works with Claude, OpenAI, LangChain, and more",
                ].map((p) => (
                  <li
                    key={p}
                    className="flex items-start gap-2.5 text-base text-muted-foreground"
                  >
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-foreground/25" />
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <Card className="overflow-hidden">
            <CardContent className="py-5">
              <p className="mb-3 font-mono text-xs text-muted-foreground">
                Python SDK
              </p>
              <pre className="overflow-x-auto font-mono text-[13px] leading-relaxed text-foreground/80 whitespace-pre">
                {WRITE_CODE}
              </pre>
            </CardContent>
          </Card>
        </div>

        {/* Step 02 — Extract */}
        <div className="mb-28 grid items-center gap-12 lg:grid-cols-2">
          <Card className="order-last overflow-hidden lg:order-first">
            <CardContent className="py-5">
              <p className="mb-4 font-mono text-xs text-muted-foreground">
                Extracted from: &ldquo;Acme Corp expects 500 units of Product Y
                by Q3&rdquo;
              </p>
              <div className="space-y-2">
                {EXTRACTED_ENTITIES.map((e) => (
                  <div
                    key={e.name}
                    className="flex items-center gap-2.5 rounded border border-border bg-muted/40 px-3 py-2.5"
                  >
                    <span
                      className="size-2 shrink-0 rounded-full"
                      style={{ backgroundColor: e.color }}
                    />
                    <span className="text-sm font-medium text-foreground">
                      {e.name}
                    </span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {e.type}
                    </span>
                  </div>
                ))}
              </div>
              <div className="mt-4 border-t border-border pt-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Relations extracted
                </p>
                <div className="space-y-1.5">
                  {EXTRACTED_RELATIONS.map((r) => (
                    <div
                      key={r.rel}
                      className="flex items-center gap-1.5 font-mono text-[13px] text-foreground/70"
                    >
                      <span className="text-foreground">{r.from}</span>
                      <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                        {r.rel}
                      </span>
                      <span className="text-foreground">{r.to}</span>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
          <div className="relative">
            <span
              aria-hidden="true"
              className="pointer-events-none absolute -left-1 -top-8 select-none font-heading text-[9rem] font-light leading-none text-foreground/6 lg:text-[11rem]"
            >
              02
            </span>
            <div className="relative">
              <h3 className="text-3xl font-medium text-foreground lg:text-4xl">
                Entities and relations are extracted
              </h3>
              <p className="mt-4 leading-relaxed text-muted-foreground">
                Claude Haiku reads your text and extracts structured entities —
                organizations, products, people, dates — and the relations
                between them. You define nothing. The LLM infers everything.
              </p>
              <ul className="mt-5 space-y-2.5">
                {[
                  "LLM-powered extraction via Claude Haiku",
                  "Entities, types, relations, and confidence scores",
                  "No schema or template configuration needed",
                ].map((p) => (
                  <li
                    key={p}
                    className="flex items-start gap-2.5 text-base text-muted-foreground"
                  >
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-foreground/25" />
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Step 03 — Resolve */}
        <div className="mb-28 grid items-center gap-12 lg:grid-cols-2">
          <div className="relative">
            <span
              aria-hidden="true"
              className="pointer-events-none absolute -left-1 -top-8 select-none font-heading text-[9rem] font-light leading-none text-foreground/6 lg:text-[11rem]"
            >
              03
            </span>
            <div className="relative">
              <h3 className="text-3xl font-medium text-foreground lg:text-4xl">
                Entities resolve onto the shared graph
              </h3>
              <p className="mt-4 leading-relaxed text-muted-foreground">
                Before writing, each entity is matched against what already
                exists using vector similarity. If &ldquo;Acme Corp&rdquo; is
                already in the graph from a different agent, the new fact
                attaches to the same node — no duplicates, no conflicting state.
              </p>
              <ul className="mt-5 space-y-2.5">
                {[
                  "Vector similarity matching across all agents",
                  "MERGE deduplication — repeated facts increment support count",
                  "Structural isolation per tenant, never mixed",
                ].map((p) => (
                  <li
                    key={p}
                    className="flex items-start gap-2.5 text-base text-muted-foreground"
                  >
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-foreground/25" />
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <Card>
            <CardContent className="py-5">
              <p className="mb-4 font-mono text-xs text-muted-foreground">
                Resolution outcome
              </p>
              <div className="space-y-3">
                <div className="rounded border border-border bg-muted/30 p-3.5">
                  <div className="flex items-center gap-2">
                    <span className="size-2 rounded-full bg-[#6366f1]" />
                    <span className="text-sm font-semibold text-foreground">
                      Meridian Corp
                    </span>
                    <span className="ml-auto rounded bg-emerald-50 px-1.5 py-0.5 text-xs font-medium text-emerald-700">
                      matched existing
                    </span>
                  </div>
                  <p className="mt-1.5 pl-4 text-sm leading-relaxed text-muted-foreground">
                    similarity 0.96 &middot; merged with entity from CRM Agent
                    write at 09:14:02
                  </p>
                </div>
                <div className="rounded border border-border bg-muted/30 p-3.5">
                  <div className="flex items-center gap-2">
                    <span className="size-2 rounded-full bg-[#f59e0b]" />
                    <span className="text-sm font-semibold text-foreground">
                      Sofia Reyes
                    </span>
                    <span className="ml-auto rounded bg-indigo-50 px-1.5 py-0.5 text-xs font-medium text-indigo-700">
                      new entity
                    </span>
                  </div>
                  <p className="mt-1.5 pl-4 text-sm leading-relaxed text-muted-foreground">
                    no match above threshold &middot; created as new Person node
                  </p>
                </div>
                <div className="rounded border border-border bg-muted/30 p-3.5">
                  <p className="font-mono text-xs text-muted-foreground">
                    Relation written
                  </p>
                  <p className="mt-1.5 font-mono text-sm text-foreground/70">
                    Sofia Reyes{" "}
                    <span className="rounded bg-muted px-1.5 py-0.5 text-xs">
                      WORKS_AT
                    </span>{" "}
                    Meridian Corp
                  </p>
                  <p className="mt-1.5 text-sm text-muted-foreground">
                    MERGE on (source, target, type) &middot; support_count +1
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Step 04 — Recall */}
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <Card className="order-last overflow-hidden lg:order-first">
            <CardContent className="py-5">
              <p className="mb-3 font-mono text-xs text-muted-foreground">
                Any agent can query
              </p>
              <pre className="overflow-x-auto font-mono text-[13px] leading-relaxed text-foreground/80 whitespace-pre">
                {RECALL_CODE}
              </pre>
            </CardContent>
          </Card>
          <div className="relative">
            <span
              aria-hidden="true"
              className="pointer-events-none absolute -left-1 -top-8 select-none font-heading text-[9rem] font-light leading-none text-foreground/6 lg:text-[11rem]"
            >
              04
            </span>
            <div className="relative">
              <h3 className="text-3xl font-medium text-foreground lg:text-4xl">
                Any agent can recall across all writers
              </h3>
              <p className="mt-4 leading-relaxed text-muted-foreground">
                A natural language query is embedded, matched to seed entities
                by similarity, then traversed one hop across the graph. The
                result contains every entity and relation contributed by every
                agent — with full provenance on each fact.
              </p>
              <ul className="mt-5 space-y-2.5">
                {[
                  "Hybrid vector + graph retrieval",
                  "Traversal from relevant entity seeds",
                  "Every fact traced to source agent and timestamp",
                ].map((p) => (
                  <li
                    key={p}
                    className="flex items-start gap-2.5 text-base text-muted-foreground"
                  >
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-foreground/25" />
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
