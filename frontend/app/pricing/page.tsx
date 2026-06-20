import Link from "next/link";
import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardTitle } from "@/components/ui/card";
import { SiteFooter } from "@/components/landing/site-footer";
import { SiteHeader } from "@/components/landing/site-header";

const TIERS = [
  {
    name: "Hobby",
    price: "Free",
    period: "",
    description:
      "For individuals and side projects exploring agent memory.",
    cta: "Start for free",
    ctaHref: "/dashboard",
    highlight: false,
    features: [
      "10,000 memories / month",
      "1 tenant",
      "1 API key",
      "REST API access",
      "MCP integration",
      "Community support",
    ],
  },
  {
    name: "Pro",
    price: "$49",
    period: "/ month",
    description:
      "For teams building production AI workflows that need more capacity.",
    cta: "Start free trial",
    ctaHref: "/dashboard",
    highlight: true,
    features: [
      "500,000 memories / month",
      "10 tenants",
      "10 API keys",
      "REST API access",
      "MCP integration",
      "Analytics dashboard",
      "Email support",
      "99.5% uptime SLA",
    ],
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description:
      "For organizations that need unlimited capacity, on-prem, and SLA guarantees.",
    cta: "Contact us",
    ctaHref: "mailto:hello@contextstore.ai",
    highlight: false,
    features: [
      "Unlimited memories",
      "Unlimited tenants",
      "Unlimited API keys",
      "On-premises deployment",
      "SSO / SAML",
      "Custom data retention",
      "Dedicated support",
      "99.9% uptime SLA",
      "Custom contracts & MSA",
    ],
  },
];

const FAQ = [
  {
    q: "What counts as a memory?",
    a: "A memory is one call to the remember() endpoint. It can contain any amount of natural language text — the system extracts multiple entities and relations from it, all attributed to that single memory write.",
  },
  {
    q: "Can I upgrade or downgrade at any time?",
    a: "Yes. You can change your plan at any time from the dashboard. Upgrades take effect immediately; downgrades apply at the end of your billing cycle.",
  },
  {
    q: "What is a tenant?",
    a: "A tenant is a structurally isolated graph. You use tenants to separate data between customers, projects, or environments. Each tenant's data is stored in its own FalkorDB graph — they are never mixed.",
  },
  {
    q: "Is there a free trial for Pro?",
    a: "Yes. The Pro tier includes a 14-day free trial with no credit card required. You get full access to all Pro features during the trial.",
  },
  {
    q: "What happens when I hit my memory limit?",
    a: "Remember() calls that exceed your monthly limit are rejected with a 429 response. Your existing data and recall() queries continue to work normally. You can upgrade at any time to restore write access.",
  },
];

export default function PricingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <main className="flex-1">
        {/* Hero */}
        <section className="mx-auto max-w-3xl px-6 py-24 text-center">
          <h1 className="text-5xl font-semibold tracking-tight text-foreground">
            Simple, transparent pricing
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-lg text-muted-foreground leading-relaxed">
            Start free. Scale as your agents do. No surprise charges, no per-seat
            fees — just memory capacity.
          </p>
        </section>

        {/* Pricing tiers */}
        <section className="border-t border-border">
          <div className="mx-auto max-w-5xl px-6 py-16">
            <div className="grid gap-5 md:grid-cols-3">
              {TIERS.map((tier) => (
                <Card
                  key={tier.name}
                  className={
                    tier.highlight
                      ? "border-foreground/25 ring-1 ring-foreground/15"
                      : ""
                  }
                >
                  <CardContent className="flex flex-col gap-5 py-6">
                    <div>
                      {tier.highlight && (
                        <span className="mb-3 inline-block rounded bg-foreground px-2 py-0.5 text-xs font-medium text-background">
                          Most popular
                        </span>
                      )}
                      <CardTitle className="text-lg text-foreground">
                        {tier.name}
                      </CardTitle>
                      <div className="mt-2 flex items-baseline gap-1">
                        <span className="text-3xl font-semibold tracking-tight text-foreground">
                          {tier.price}
                        </span>
                        {tier.period && (
                          <span className="text-sm text-muted-foreground">
                            {tier.period}
                          </span>
                        )}
                      </div>
                      <CardDescription className="mt-2 leading-relaxed">
                        {tier.description}
                      </CardDescription>
                    </div>
                    <Button
                      variant={tier.highlight ? "default" : "outline"}
                      className="w-full"
                      render={<Link href={tier.ctaHref} />}
                    >
                      {tier.cta}
                    </Button>
                    <ul className="space-y-2.5">
                      {tier.features.map((feature) => (
                        <li
                          key={feature}
                          className="flex items-start gap-2.5 text-sm text-muted-foreground"
                        >
                          <Check className="mt-0.5 size-3.5 shrink-0 text-foreground/60" />
                          {feature}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="border-t border-border">
          <div className="mx-auto max-w-3xl px-6 py-20">
            <h2 className="mb-10 text-2xl font-semibold tracking-tight text-foreground">
              Frequently asked questions
            </h2>
            <div className="space-y-8">
              {FAQ.map((item) => (
                <div key={item.q} className="border-b border-border pb-8 last:border-0 last:pb-0">
                  <h3 className="font-semibold text-foreground">{item.q}</h3>
                  <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                    {item.a}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Enterprise callout */}
        <section className="border-t border-border">
          <div className="mx-auto max-w-3xl px-6 py-16 text-center">
            <h2 className="text-xl font-semibold text-foreground">
              Need something custom?
            </h2>
            <p className="mt-2 text-muted-foreground">
              We work directly with enterprise teams on capacity, compliance,
              and deployment requirements.
            </p>
            <Button
              variant="outline"
              size="lg"
              className="mt-6"
              render={<Link href="mailto:hello@contextstore.ai" />}
            >
              Talk to us
            </Button>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
