const STATS = [
  {
    value: "< 100ms",
    label: "Average recall latency",
    sub: "across shared tenant graphs",
  },
  {
    value: "2",
    label: "Endpoints to integrate",
    sub: "remember() and recall()",
  },
  {
    value: "∞",
    label: "Agents per tenant",
    sub: "write and read concurrently",
  },
  {
    value: "100%",
    label: "Provenance coverage",
    sub: "every fact traced to its source",
  },
];

export function StatsSection() {
  return (
    <section className="bg-section-alt">
      <div className="mx-auto max-w-6xl px-6 py-16">
        <div className="grid grid-cols-2 gap-10 md:grid-cols-4">
          {STATS.map((stat) => (
            <div key={stat.label} className="flex flex-col gap-1.5">
              <span className="font-heading text-5xl font-light text-foreground">
                {stat.value}
              </span>
              <span className="text-sm font-medium text-foreground/75">
                {stat.label}
              </span>
              <span className="text-xs text-muted-foreground">{stat.sub}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
