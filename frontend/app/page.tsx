import { AgentsSection } from "@/components/landing/agents-section";
import { GraphSection } from "@/components/landing/graph-section";
import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { LogosStrip } from "@/components/landing/logos-strip";
import { MultiAgentSection } from "@/components/landing/multi-agent-section";
import { SiteFooter } from "@/components/landing/site-footer";
import { SiteHeader } from "@/components/landing/site-header";
import { StatsSection } from "@/components/landing/stats-section";
import { WaitlistFooter } from "@/components/landing/waitlist-footer";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main className="flex-1">
        <Hero />
        <LogosStrip />
        <GraphSection />
        <HowItWorks />
        <AgentsSection />
        <MultiAgentSection />
        <StatsSection />
        <WaitlistFooter />
      </main>
      <SiteFooter />
    </div>
  );
}
