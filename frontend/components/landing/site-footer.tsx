import Link from "next/link";

const FOOTER_SECTIONS = [
  {
    title: "Product",
    links: [
      { label: "Features", href: "/features" },
      { label: "Pricing", href: "/pricing" },
      { label: "Changelog", href: "#" },
      { label: "Roadmap", href: "#" },
    ],
  },
  {
    title: "Developers",
    links: [
      { label: "Documentation", href: "/docs" },
      { label: "API Reference", href: "/api-reference" },
      { label: "MCP Integration", href: "/docs#mcp" },
      { label: "SDKs", href: "/docs#sdks" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "#" },
      { label: "Blog", href: "#" },
      { label: "Careers", href: "#" },
      { label: "Contact", href: "#" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy Policy", href: "#" },
      { label: "Terms of Service", href: "#" },
      { label: "Security", href: "#" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="bg-section-alt">
      <div className="mx-auto max-w-6xl px-6 py-14">
        <div className="grid gap-10 md:grid-cols-5">
          <div className="md:col-span-1">
            <Link
              href="/"
              className="font-mono text-sm font-semibold tracking-tight text-foreground"
            >
              contextstore
            </Link>
            <p className="mt-3 text-xs text-muted-foreground leading-relaxed max-w-[160px]">
              GraphRAG memory layer for production AI workflows.
            </p>
          </div>
          {FOOTER_SECTIONS.map((section) => (
            <div key={section.title}>
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-foreground/60">
                {section.title}
              </h3>
              <ul className="space-y-2">
                {section.links.map((link) => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-12 flex flex-col items-start justify-between gap-4 pt-6 sm:flex-row sm:items-center">
          <p className="text-xs text-muted-foreground">
            &copy; 2026 ContextStore. All rights reserved.
          </p>
          <div className="flex items-center gap-5">
            <Link
              href="#"
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              Privacy
            </Link>
            <Link
              href="#"
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              Terms
            </Link>
            <Link
              href="#"
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              Security
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
