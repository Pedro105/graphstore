import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  GlowSection,
  landingRowClassName,
} from "@/components/landing/section-glow";

const DEMO_AGENTS = [
  {
    name: "CRM Agent",
    color: "#6366f1",
    desc: "Syncs account health signals from your CRM. Tracks renewal dates, seat counts, primary contacts, and deal stages as they change.",
    memories: "387",
  },
  {
    name: "Support Agent",
    color: "#f59e0b",
    desc: "Monitors open tickets and flags critical issues affecting enterprise accounts. Writes severity, affected features, and time-to-resolution estimates.",
    memories: "241",
  },
  {
    name: "Product Agent",
    color: "#10b981",
    desc: "Tracks release timelines and links fix commits to customer-reported issues. Knows which version resolves which problem and when it ships.",
    memories: "162",
  },
  {
    name: "Account Agent",
    color: "#8b5cf6",
    desc: "Records expansion signals, meeting notes, and customer sentiment. Captures buying intent, blockers, and next-step commitments from calls.",
    memories: "94",
  },
];

export function AgentsSection() {
  return (
    <GlowSection
      className="bg-section-alt"
      glows={[{ placement: "bottom-right", variant: "on-soft", size: "md" }]}
    >
      <div className="relative mx-auto max-w-6xl px-6 py-20">
        <div className="grid items-start gap-16 lg:grid-cols-2">
          {/* Left: text */}
          <div className="lg:sticky lg:top-24">
            <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Agent registry
            </span>
            <h2 className="mt-2 text-4xl font-light leading-tight text-foreground lg:text-5xl">
              Register your agents.
              <br />
              <span className="italic">Let them share.</span>
            </h2>
            <p className="mt-5 text-base leading-relaxed text-muted-foreground">
              Name your agents once. Every write they make is tagged with their
              identity, so the graph knows who contributed what. Any agent can
              read anything written by any other — no coordination, no shared
              state, no message passing.
            </p>
            <p className="mt-4 text-base leading-relaxed text-muted-foreground">
              The agent registry in your dashboard gives you a single place to
              define, audit, and manage every writer in your tenant. See memory
              counts, recent writes, and which entities each agent owns.
            </p>
            <ul className="mt-6 space-y-3">
              {[
                "Per-agent provenance on every fact",
                "Unlimited agents per tenant",
                "Register via API or dashboard",
                "Scoped recall — filter by agent, user, or project",
              ].map((point) => (
                <li
                  key={point}
                  className="flex items-start gap-2.5 text-base text-muted-foreground"
                >
                  <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-foreground/30" />
                  {point}
                </li>
              ))}
            </ul>
            <div className="mt-8">
              <Button
                variant="outline"
                size="sm"
                render={<Link href="/dashboard/agents" />}
              >
                View agent registry
              </Button>
            </div>
          </div>

          {/* Right: agent cards */}
          <div className="space-y-3">
            {DEMO_AGENTS.map((agent) => (
              <div
                key={agent.name}
                className={`rounded-lg border border-border/50 bg-card p-5 transition-colors hover:border-foreground/15 ${landingRowClassName}`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-2.5">
                    <span
                      className="mt-0.5 size-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: agent.color }}
                    />
                    <span className="font-semibold text-foreground">
                      {agent.name}
                    </span>
                  </div>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {agent.memories} memories
                  </span>
                </div>
                <p className="mt-3 pl-5 text-base leading-relaxed text-muted-foreground">
                  {agent.desc}
                </p>
              </div>
            ))}
            <div className="rounded border border-dashed border-border p-5 text-center">
              <p className="text-base text-muted-foreground">
                + Add a new agent via API or dashboard
              </p>
            </div>
          </div>
        </div>
      </div>
    </GlowSection>
  );
}
