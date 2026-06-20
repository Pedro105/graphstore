import Link from "next/link";

import { Button } from "@/components/ui/button";

const NAV_LINKS = [
  { label: "Features", href: "/features" },
  { label: "Pricing", href: "/pricing" },
  { label: "Docs", href: "/docs" },
  { label: "API", href: "/api-reference" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 bg-background/90 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
        <Link
          href="/"
          className="font-mono text-sm font-semibold tracking-tight text-foreground"
        >
          contextstore
        </Link>
        <nav className="hidden items-center md:flex">
          {NAV_LINKS.map((link) => (
            <Button
              key={link.href}
              variant="ghost"
              size="sm"
              render={<Link href={link.href} />}
              className="text-muted-foreground hover:text-foreground"
            >
              {link.label}
            </Button>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            render={<Link href="/docs" />}
            className="hidden sm:inline-flex"
          >
            Documentation
          </Button>
          <Button size="sm" render={<Link href="/dashboard" />}>
            Get started
          </Button>
        </div>
      </div>
    </header>
  );
}
