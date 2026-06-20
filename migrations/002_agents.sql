-- Agents: named writers to a tenant's graph.
--
-- A frontend/product concept (the registry the dashboard's "source" picker and
-- multi-agent story read from), not part of the graph engine -- so it lives in
-- Postgres alongside the other relational/auth tables, scoped by tenant_id the
-- same way api_keys is. tenant_id is the authenticated tenant from the API key;
-- there is no cross-tenant access.
--
--   psql "$DATABASE_URL" -f migrations/002_agents.sql

CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON agents(tenant_id);
