-- ContextStore initial Postgres schema.
--
-- FalkorDB remains the graph + vector store; Postgres holds only the
-- relational concerns that auth needs: who owns what, which API keys exist
-- (and the tenant they resolve to), and a usage log for accounting.
--
-- Runnable against a fresh Supabase/Postgres instance:
--   psql "$DATABASE_URL" -f migrations/001_initial.sql
--
-- gen_random_uuid() comes from pgcrypto, which Supabase enables by default;
-- the explicit CREATE EXTENSION keeps this runnable on a bare Postgres too.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id TEXT NOT NULL,
    key_hash TEXT UNIQUE NOT NULL,  -- bcrypt hash of the actual key
    name TEXT,                       -- human label e.g. "production", "dev"
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ           -- NULL = active
);

CREATE TABLE usage_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_id UUID NOT NULL REFERENCES api_keys(id),
    tenant_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,          -- "/v1/memories" or "/v1/recall"
    tokens_used INT,                 -- populated if an LLM call was made
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON api_keys(key_hash);
CREATE INDEX ON usage_log(api_key_id, created_at);
