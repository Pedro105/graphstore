import type { NextConfig } from "next";

// Keep in sync with DOCS_URL in lib/links.ts. Hardcoded here because next.config
// is evaluated by Node before the app's module/alias resolution is set up.
const DOCS_URL = "https://graphdb.mintlify.app";

const nextConfig: NextConfig = {
  // The hand-built /docs page was migrated to the hosted Mintlify site. All
  // in-app links now point straight at DOCS_URL, but redirect the old internal
  // path too so any stale bookmark or inbound link lands on the live docs.
  // Temporary (307) rather than permanent: the Mintlify URL is not yet final.
  async redirects() {
    return [
      { source: "/docs", destination: DOCS_URL, permanent: false },
      {
        source: "/docs/:path*",
        destination: `${DOCS_URL}/:path*`,
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
