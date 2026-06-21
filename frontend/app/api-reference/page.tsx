import { ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardTitle } from "@/components/ui/card";
import { SiteFooter } from "@/components/landing/site-footer";
import { SiteHeader } from "@/components/landing/site-header";
import { DOCS_URL } from "@/lib/links";

const BASE_URL = "https://api.contextstore.ai";

const ENDPOINTS = [
  {
    method: "POST",
    path: "/v1/memories",
    title: "Remember",
    description:
      "Write a natural language memory to the graph. ContextStore extracts entities and relations using an LLM and merges them into the tenant graph with full provenance.",
    request: {
      fields: [
        {
          name: "text",
          type: "string",
          required: true,
          description: "Natural language text to store.",
        },
        {
          name: "scope",
          type: "Scope",
          required: true,
          description: "Tenant and optional agent/user/project context.",
        },
        {
          name: "scope.tenant_id",
          type: "string",
          required: true,
          description:
            "The tenant graph to write into. Must be a non-empty string.",
        },
        {
          name: "scope.agent_id",
          type: "string",
          required: false,
          description: "Identifier of the writing agent.",
        },
        {
          name: "scope.user_id",
          type: "string",
          required: false,
          description: "Identifier of the end user.",
        },
      ],
    },
    response: `{
  "memory_id": "mem_01JABCDEF...",
  "entities_written": 3,
  "relations_written": 2
}`,
    example: `curl -X POST ${BASE_URL}/v1/memories \\
  -H "Authorization: Bearer sk-..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "text": "Acme Corp expects 500 units of Product Y by Q3",
    "scope": {
      "tenant_id": "your-tenant",
      "agent_id": "crm-agent"
    }
  }'`,
  },
  {
    method: "POST",
    path: "/v1/recall",
    title: "Recall",
    description:
      "Query the graph with a natural language question. ContextStore embeds the query, finds similar entity seeds, traverses one hop from each seed, and returns a structured RecallResult.",
    request: {
      fields: [
        {
          name: "query",
          type: "string",
          required: true,
          description: "Natural language question to answer from the graph.",
        },
        {
          name: "scope",
          type: "Scope",
          required: true,
          description:
            "Tenant scope to query. Optional sub-scope keys filter results in Python after retrieval.",
        },
        {
          name: "top_k",
          type: "integer",
          required: false,
          description:
            "Maximum number of seed entities to use. Defaults to 5.",
        },
      ],
    },
    response: `{
  "query": "What does Acme Corp need?",
  "entities": [
    {
      "id": "ent_...",
      "name": "Acme Corp",
      "type": "Organization",
      "properties": { "region": "US-West" }
    }
  ],
  "relations": [
    {
      "source_id": "ent_...",
      "target_id": "ent_...",
      "type": "EXPECTS",
      "properties": { "quantity": 500, "unit": "units" }
    }
  ],
  "provenance": [
    {
      "memory_id": "mem_01JABCDEF...",
      "agent_id": "crm-agent",
      "written_at": "2026-06-18T14:02:01Z"
    }
  ]
}`,
    example: `curl -X POST ${BASE_URL}/v1/recall \\
  -H "Authorization: Bearer sk-..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "What does Acme Corp need?",
    "scope": { "tenant_id": "your-tenant" },
    "top_k": 5
  }'`,
  },
  {
    method: "GET",
    path: "/v1/health",
    title: "Health check",
    description:
      "Returns the operational status of the API and its graph backend. Useful for uptime monitoring.",
    request: { fields: [] },
    response: `{
  "status": "ok",
  "graph_store": "ok",
  "latency_ms": 4
}`,
    example: `curl ${BASE_URL}/v1/health \\
  -H "Authorization: Bearer sk-..."`,
  },
];

const METHOD_COLORS: Record<string, string> = {
  GET: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  POST: "bg-indigo-50 text-indigo-700 border border-indigo-200",
  DELETE: "bg-red-50 text-red-700 border border-red-200",
};

export default function ApiReferencePage() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main className="flex-1">
        {/* Hero */}
        <section className="border-b border-border">
          <div className="mx-auto max-w-5xl px-6 py-14">
            <div className="flex items-start justify-between gap-8">
              <div>
                <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  API Reference — v1
                </span>
                <h1 className="mt-2 text-4xl font-semibold tracking-tight text-foreground">
                  REST API
                </h1>
                <p className="mt-3 max-w-xl text-muted-foreground leading-relaxed">
                  The ContextStore API is a simple HTTP REST API. Authenticate
                  with a bearer token, and use two endpoints — remember and
                  recall — to give any agent persistent, queryable memory.
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-5"
                  render={
                    <a
                      href={DOCS_URL}
                      target="_blank"
                      rel="noopener noreferrer"
                    />
                  }
                >
                  Back to docs
                  <ArrowRight className="size-3.5" />
                </Button>
              </div>
            </div>
          </div>
        </section>

        {/* Auth */}
        <section className="border-b border-border">
          <div className="mx-auto max-w-5xl px-6 py-12">
            <h2 className="mb-4 text-xl font-semibold text-foreground">
              Authentication
            </h2>
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  All API requests require a bearer token in the
                  Authorization header. You can create and manage API keys
                  from the dashboard. Keep your keys secret — they have full
                  write access to your tenant data.
                </p>
                <p className="mt-3 text-sm text-muted-foreground">
                  Base URL:{" "}
                  <span className="font-mono text-foreground">
                    {BASE_URL}
                  </span>
                </p>
              </div>
              <Card>
                <CardContent className="py-4">
                  <pre className="font-mono text-xs text-foreground/80 leading-relaxed whitespace-pre">
                    {`Authorization: Bearer sk-your-api-key

# All requests must include:
Content-Type: application/json`}
                  </pre>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        {/* Endpoints */}
        <section>
          <div className="mx-auto max-w-5xl px-6 py-12">
            <h2 className="mb-8 text-xl font-semibold text-foreground">
              Endpoints
            </h2>
            <div className="space-y-12">
              {ENDPOINTS.map((endpoint) => (
                <div
                  key={endpoint.path}
                  className="border-b border-border pb-12 last:border-0 last:pb-0"
                >
                  {/* Endpoint header */}
                  <div className="mb-5 flex items-center gap-3">
                    <span
                      className={`rounded px-2 py-0.5 font-mono text-xs font-semibold ${METHOD_COLORS[endpoint.method]}`}
                    >
                      {endpoint.method}
                    </span>
                    <span className="font-mono text-sm text-foreground">
                      {endpoint.path}
                    </span>
                  </div>
                  <h3 className="mb-1 text-lg font-semibold text-foreground">
                    {endpoint.title}
                  </h3>
                  <p className="mb-6 text-sm text-muted-foreground leading-relaxed max-w-2xl">
                    {endpoint.description}
                  </p>

                  <div className="grid gap-5 lg:grid-cols-2">
                    <div className="space-y-4">
                      {endpoint.request.fields.length > 0 && (
                        <div>
                          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-foreground/60">
                            Request body
                          </p>
                          <div className="space-y-2">
                            {endpoint.request.fields.map((field) => (
                              <Card key={field.name} size="sm">
                                <CardContent className="flex flex-col gap-0.5 py-2.5">
                                  <div className="flex items-center gap-2">
                                    <span className="font-mono text-xs text-foreground">
                                      {field.name}
                                    </span>
                                    <span className="font-mono text-xs text-muted-foreground">
                                      {field.type}
                                    </span>
                                    {field.required && (
                                      <span className="rounded bg-foreground/8 px-1.5 py-0.5 text-xs text-foreground/60">
                                        required
                                      </span>
                                    )}
                                  </div>
                                  <CardDescription className="text-xs">
                                    {field.description}
                                  </CardDescription>
                                </CardContent>
                              </Card>
                            ))}
                          </div>
                        </div>
                      )}
                      <div>
                        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-foreground/60">
                          Response
                        </p>
                        <Card>
                          <CardContent className="py-4">
                            <pre className="overflow-x-auto font-mono text-xs text-foreground/80 leading-relaxed whitespace-pre">
                              {endpoint.response}
                            </pre>
                          </CardContent>
                        </Card>
                      </div>
                    </div>
                    <div>
                      <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-foreground/60">
                        Example
                      </p>
                      <Card>
                        <CardContent className="py-4">
                          <pre className="overflow-x-auto font-mono text-xs text-foreground/80 leading-relaxed whitespace-pre">
                            {endpoint.example}
                          </pre>
                        </CardContent>
                      </Card>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Error codes */}
        <section className="border-t border-border">
          <div className="mx-auto max-w-5xl px-6 py-12">
            <h2 className="mb-6 text-xl font-semibold text-foreground">
              Error codes
            </h2>
            <div className="grid gap-3 md:grid-cols-2">
              {[
                {
                  code: "400",
                  title: "Bad Request",
                  description: "Missing or invalid request body.",
                },
                {
                  code: "401",
                  title: "Unauthorized",
                  description: "Missing or invalid API key.",
                },
                {
                  code: "403",
                  title: "Forbidden",
                  description: "Key does not have access to the requested tenant.",
                },
                {
                  code: "422",
                  title: "Unprocessable Entity",
                  description: "Request body failed validation.",
                },
                {
                  code: "429",
                  title: "Too Many Requests",
                  description:
                    "Monthly memory limit reached. Upgrade your plan or wait for reset.",
                },
                {
                  code: "500",
                  title: "Internal Server Error",
                  description: "Something went wrong on our end. Retry with exponential backoff.",
                },
              ].map((error) => (
                <Card key={error.code} size="sm">
                  <CardContent className="flex items-start gap-3 py-3">
                    <span className="shrink-0 font-mono text-sm font-semibold text-foreground">
                      {error.code}
                    </span>
                    <div>
                      <CardTitle className="text-sm text-foreground">
                        {error.title}
                      </CardTitle>
                      <CardDescription className="mt-0.5 text-xs">
                        {error.description}
                      </CardDescription>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
