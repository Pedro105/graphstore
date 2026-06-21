// External links that live outside this Next.js app. Single source of truth so
// every docs reference (marketing pages + dashboard) points at one place and a
// URL change is a one-line edit, not a codebase-wide hunt.

// The hosted Mintlify documentation site.
export const DOCS_URL = "https://graphdb.mintlify.app";

// Public base URL of the hosted backend API (matches the OpenAPI spec the docs
// site reads). Used in copy-able example snippets shown to users.
export const API_BASE_URL = "https://contextstore-api.fly.dev";

// Deep links into specific docs pages (match docs-site/ page slugs). NB: the
// MCP page is served at /mcp-server, not /mcp -- Mintlify reserves /mcp for its
// hosted MCP endpoint, which would shadow a page with that slug.
export const DOCS_MCP_URL = `${DOCS_URL}/mcp-server`;
