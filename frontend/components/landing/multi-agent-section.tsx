import { Card, CardContent } from "@/components/ui/card";

const FEED = [
  {
    time: "09:14:02.381",
    agent: "CRM Agent",
    color: "#6366f1",
    text: "wrote: Meridian Corp (850 seats) renewing in 23 days. Contact: Sofia Reyes, VP Eng. ARR $180k.",
  },
  {
    time: "09:14:18.594",
    agent: "Support Agent",
    color: "#f59e0b",
    text: "wrote: 3 open P1s for Meridian. Data export API rate limiting breaking nightly batch jobs since June 12.",
  },
  {
    time: "09:14:31.017",
    agent: "Product Agent",
    color: "#10b981",
    text: "wrote: Rate limit fix in v3.4.0, shipping June 24 — 6 days before Meridian renewal date.",
  },
  {
    time: "09:14:47.229",
    agent: "Account Agent",
    color: "#8b5cf6",
    text: "wrote: Sofia Reyes indicated 200-seat expansion if export resolved. Est. expansion value $42k ARR.",
  },
];

export function MultiAgentSection() {
  return (
    <section className="bg-background">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <div className="grid items-center gap-12 md:grid-cols-2">
          <div>
            <h2 className="text-4xl font-light leading-tight text-foreground lg:text-5xl">
              Built for{" "}
              <span className="italic">concurrent writes</span>
            </h2>
            <p className="mt-4 text-base leading-relaxed text-muted-foreground">
              This isn&apos;t a single conversation&apos;s memory. Four
              separate agents — CRM, support, product, and account — each
              wrote independently about the same customer. ContextStore
              resolved their writes onto shared entities automatically.
            </p>
            <ul className="mt-6 space-y-3">
              {[
                "Full provenance on every fact — know which agent wrote what",
                "Concurrent writes with no coordination overhead",
                "Entity resolution merges overlapping context automatically",
              ].map((point) => (
                <li
                  key={point}
                  className="flex items-start gap-2.5 text-base text-muted-foreground"
                >
                  <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-foreground/35" />
                  {point}
                </li>
              ))}
            </ul>
          </div>
          <Card>
            <CardContent className="flex flex-col gap-4 py-5 font-mono text-sm">
              {FEED.map((entry) => (
                <div key={entry.time} className="flex items-start gap-2.5">
                  <span className="shrink-0 tabular-nums text-muted-foreground">
                    {entry.time}
                  </span>
                  <span
                    className="mt-1.5 size-1.5 shrink-0 rounded-full"
                    style={{ backgroundColor: entry.color }}
                  />
                  <span className="text-foreground/80">
                    <span className="font-semibold text-foreground">
                      {entry.agent}
                    </span>{" "}
                    {entry.text}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}
