-- Projects + memory audit log.
--
-- Formalizes "a project" as a first-class concept: a named owner of one
-- tenant_id (= one FalkorDB graph). Until now tenant_id was just a free-string
-- column on api_keys with nothing owning the concept; this gives every tenant a
-- row with a name, an owner, and a place for the operator admin view to hang
-- per-project metadata off.
--
--   psql "$DATABASE_URL" -f migrations/003_projects.sql
--
-- Safe to run once against an existing database that already has users/api_keys
-- rows: the backfill below materializes a project for every tenant_id already
-- in use before the foreign key is added, so no existing key is orphaned.

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT UNIQUE NOT NULL,
    owner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Backfill: one project per distinct tenant_id already present on api_keys,
-- owned by the earliest-created key's user for that tenant and given a
-- generated name. DISTINCT ON keeps a single row per tenant_id; ON CONFLICT
-- makes the whole migration safe to re-run.
INSERT INTO projects (tenant_id, owner_user_id, name)
SELECT DISTINCT ON (tenant_id) tenant_id, user_id, 'Project ' || tenant_id
FROM api_keys
ORDER BY tenant_id, created_at
ON CONFLICT (tenant_id) DO NOTHING;

-- api_keys.tenant_id now references a real project. No ON DELETE CASCADE here:
-- the admin "wipe tenant" path deletes dependent rows explicitly and in order
-- (see db/postgres.delete_project_cascade) so the destruction is auditable
-- rather than an implicit cascade, and an accidental project delete can't
-- silently take a tenant's keys with it.
ALTER TABLE api_keys
    ADD CONSTRAINT api_keys_tenant_id_fkey
    FOREIGN KEY (tenant_id) REFERENCES projects(tenant_id);

-- Audit log of raw memory writes. The graph engine discards the original
-- natural-language content once entities/relations are extracted (the write
-- path only persists the extracted graph), so this Postgres table is the only
-- record of "what was actually submitted" versus "what got extracted". It is
-- deliberately decoupled from the graph: a row is written here alongside every
-- /v1/memories POST, never read on the retrieval path.
CREATE TABLE memory_writes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL REFERENCES projects(tenant_id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    raw_content TEXT NOT NULL,
    extracted_entity_count INT NOT NULL DEFAULT 0,
    extracted_relation_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON projects(owner_user_id);
CREATE INDEX ON memory_writes(tenant_id, created_at);
