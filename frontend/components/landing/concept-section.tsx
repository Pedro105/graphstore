import { ArrowRight } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

const DEMO_AGENTS = [
  { name: "CRM Agent", color: "#6366f1" },
  { name: "Supplier Agent", color: "#f59e0b" },
  { name: "Pricing Agent", color: "#10b981" },
  { name: "Fulfillment Agent", color: "#8b5cf6" },
];

export function ConceptSection() {
  return (
    <section className="border-t border-border">
      <div className="mx-auto max-w-5xl px-6 py-20">
        <div className="mb-12 text-center">
          <h2 className="text-3xl font-semibold tracking-tight text-foreground">
            One graph, written by everyone
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-muted-foreground leading-relaxed">
            Every agent writes into the same tenant graph. When two agents
            mention the same customer, product, or supplier, ContextStore
            resolves them onto one shared entity instead of two disconnected
            records. No duplicate data. No stale context.
          </p>
        </div>
        <div className="flex flex-col items-center gap-8 md:flex-row md:justify-center">
          <div className="grid grid-cols-2 gap-3">
            {DEMO_AGENTS.map((agent) => (
              <Card key={agent.name} size="sm" className="w-44">
                <CardContent className="flex items-center gap-2">
                  <span
                    className="size-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: agent.color }}
                  />
                  <span className="truncate text-sm font-medium text-foreground">
                    {agent.name}
                  </span>
                </CardContent>
              </Card>
            ))}
          </div>
          <ArrowRight className="size-5 shrink-0 rotate-90 text-muted-foreground md:rotate-0" />
          <Card className="w-56 border border-border bg-card">
            <CardContent className="flex flex-col items-center gap-2 py-6 text-center">
              <span className="font-mono text-xs text-muted-foreground">
                tenant_demo
              </span>
              <span className="text-base font-semibold text-foreground">
                Shared memory graph
              </span>
              <span className="text-xs text-muted-foreground">
                Entities resolved &amp; merged
              </span>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}
