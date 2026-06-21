import Link from "next/link";

import { Button } from "@/components/ui/button";
import { sectionGlowStyle } from "@/components/landing/section-glow";
import { DOCS_URL } from "@/lib/links";

const ACTIVITY_FEED = [
  {
    time: "09:14:02",
    agent: "CRM Agent",
    color: "#6366f1",
    text: "Meridian Corp (850 seats, enterprise) is up for renewal in 23 days. Primary contact: Sofia Reyes, VP Engineering. Current ARR $180k.",
  },
  {
    time: "09:14:18",
    agent: "Support Agent",
    color: "#f59e0b",
    text: "3 open P1 tickets for Meridian. Most recent: data export API rate limiting is breaking their nightly batch jobs since June 12.",
  },
  {
    time: "09:14:31",
    agent: "Product Agent",
    color: "#10b981",
    text: "Data export rate limit fix is in v3.4.0, shipping June 24 — 6 days before Meridian's renewal date.",
  },
  {
    time: "09:14:47",
    agent: "Account Agent",
    color: "#8b5cf6",
    text: "Sofia Reyes flagged 200-seat expansion interest if the export issues are resolved. Estimated expansion value: $42k ARR.",
  },
];

export function Hero() {
  return (
    <div
      data-section-glow=""
      className="landing-glow-host relative bg-transparent"
      style={sectionGlowStyle([
        { placement: "center-right", variant: "on-light", size: "lg" },
        { placement: "center-left", variant: "on-light", size: "md" },
      ])}
    >
      <div className="relative z-[1] mx-auto max-w-6xl px-6 py-28 lg:py-36">
        <div className="grid items-center gap-14 lg:grid-cols-2">
          {/* Left: headline and CTAs */}
          <div>
            <span className="inline-flex items-center gap-2 rounded border border-border bg-card/80 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur-sm">
              <span className="size-1.5 rounded-full bg-emerald-500" />
              GraphRAG memory layer for AI workflows
            </span>
            <h1 className="mt-6 text-6xl font-light leading-[1.04] text-foreground lg:text-7xl">
              Many agents.
              <br />
              <span className="italic">One shared memory.</span>
            </h1>
            <p className="mt-6 max-w-md text-lg leading-relaxed text-muted-foreground">
              Agents, jobs, and AI features write structured knowledge to a
              shared graph — with provenance on every fact. Query across every
              writer, any time.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Button size="lg" render={<Link href="/dashboard" />}>
                Start building
              </Button>
              <Button
                size="lg"
                variant="outline"
                render={
                  <a
                    href={DOCS_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                  />
                }
              >
                Read the docs
              </Button>
            </div>
            <p className="mt-4 text-sm text-muted-foreground">
              Free tier available &middot; No credit card required
            </p>
          </div>

          {/* Right: live activity feed */}
          <div className="overflow-hidden rounded-xl border border-border/60 bg-card/95 shadow-[0_1px_2px_rgba(26,26,26,0.04),0_8px_28px_rgba(26,26,26,0.06)] backdrop-blur-sm">
            <div className="flex items-center justify-between border-b border-border bg-secondary px-4 py-3">
              <span className="font-mono text-sm font-medium text-foreground/70">
                tenant_saas_platform
              </span>
              <div className="flex items-center gap-1.5">
                <span className="size-1.5 animate-pulse rounded-full bg-emerald-500" />
                <span className="text-sm text-muted-foreground">
                  4 agents active
                </span>
              </div>
            </div>
            <div className="divide-y divide-border">
              {ACTIVITY_FEED.map((entry, i) => (
                <div key={i} className="flex gap-3 px-4 py-4">
                  <span className="mt-0.5 shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
                    {entry.time}
                  </span>
                  <span
                    className="mt-2 size-1.5 shrink-0 rounded-full"
                    style={{ backgroundColor: entry.color }}
                  />
                  <div>
                    <span className="text-sm font-semibold text-foreground">
                      {entry.agent}
                    </span>
                    <p className="mt-0.5 text-sm leading-relaxed text-muted-foreground">
                      {entry.text}
                    </p>
                  </div>
                </div>
              ))}
            </div>
            <div className="bg-muted/50 px-4 py-3">
              <span className="font-mono text-xs text-muted-foreground">
                8 entities resolved &middot; 8 relations written &middot; 4
                writes
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
