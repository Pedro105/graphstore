const FRAMEWORKS = [
  "Claude",
  "OpenAI",
  "LangChain",
  "LlamaIndex",
  "AutoGen",
  "CrewAI",
  "Vercel AI SDK",
  "LangGraph",
];

export function LogosStrip() {
  return (
    <section className="bg-section-alt py-7">
      <div className="mx-auto max-w-5xl px-6">
        <p className="mb-5 text-center text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/55">
          Works with any agent framework or orchestrator
        </p>
        <div className="flex flex-wrap items-center justify-center gap-x-9 gap-y-3">
          {FRAMEWORKS.map((name) => (
            <span
              key={name}
              className="text-sm font-medium text-muted-foreground/60"
            >
              {name}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
