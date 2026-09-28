import Link from "next/link";

import { DOCS_MCP_URL, DOCS_URL } from "@/lib/links";

const FOOTER_SECTIONS = [
  {
    title: "Developers",
    links: [
      { label: "Documentation", href: DOCS_URL, external: true },
      { label: "API Reference", href: "/api-reference" },
      { label: "MCP Integration", href: DOCS_MCP_URL, external: true },
    ],
  },
  {
    title: "Source",
    links: [
      { label: "GitHub", href: "https://github.com/Pedro105/graphstore", external: true },
      { label: "License (MIT)", href: "https://github.com/Pedro105/graphstore/blob/main/LICENSE", external: true },
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
                    {"external" in link && link.external ? (
                      <a
                        href={link.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                      >
                        {link.label}
                      </a>
                    ) : (
                      <Link
                        href={link.href}
                        className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                      >
                        {link.label}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-12 pt-6">
          <p className="text-xs text-muted-foreground">
            ContextStore — a research project by Pedro Costa. MIT License.
          </p>
        </div>
      </div>
    </footer>
  );
}
