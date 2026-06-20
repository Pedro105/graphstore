# ContextStore

A GraphRAG-based memory layer for AI workflows. See `docs/architecture.md`
for the full design.

## Run

### Backend

Requires FalkorDB running locally (default port):

```bash
docker run -p 6379:6379 -p 3000:3000 falkordb/falkordb:latest
```

Then, from the repo root:

```bash
cp .env.example .env   # fill in ANTHROPIC_API_KEY at minimum
uv sync
uv run uvicorn contextstore.api.app:app --reload
```

Verify it's up:

```bash
curl localhost:8000/health
curl localhost:8000/ready
```

### Authentication & API keys

Every `/v1/` route requires `Authorization: Bearer <key>`; the key resolves
to a `tenant_id` in Postgres, which is never caller-supplied. Set up:

```bash
# 1. Apply the schema to your Postgres/Supabase instance
psql "$DATABASE_URL" -f migrations/001_initial.sql

# 2. Set DATABASE_URL and ADMIN_TOKEN in .env, then (re)start the backend

# 3. Create a user (manual insert, while solo)
psql "$DATABASE_URL" -c "INSERT INTO users (email) VALUES ('you@example.com') RETURNING id;"

# 4. Mint an API key for that user + tenant (admin-token protected). The raw
#    key is shown once and never stored — only its bcrypt hash is persisted.
curl -X POST localhost:8000/v1/keys \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "<uuid-from-step-3>", "tenant_id": "your_tenant", "name": "dev"}'

# Revoke a key:
curl -X DELETE localhost:8000/v1/keys/<key_id> -H "Authorization: Bearer $ADMIN_TOKEN"
```

Per-key rate limits (`RATE_LIMIT_RECALL`, `RATE_LIMIT_MEMORIES`, requests/min)
return `429` with a `Retry-After` header when exceeded. If `DATABASE_URL` is
unset the `/v1/` routes return `503` rather than running unauthenticated.

### Frontend

```bash
cd frontend
cp .env.example .env.local
pnpm install
pnpm dev
```

Opens at `http://localhost:3000` (or the next available port).

### MCP server (Claude Code / Claude Desktop)

Exposes `remember`/`recall` as MCP tools (`contextstore_remember`,
`contextstore_recall`) over the running FastAPI server. Requires the
backend to be running (see above) and `CONTEXTSTORE_API_KEY` set to a
ContextStore API key (`csk_live_...`). The server sends it as
`Authorization: Bearer <key>` on every call, and the backend derives the
tenant from it — the MCP server no longer sets a tenant/scope itself. Mint
a key via `POST /v1/keys` (see "API keys" below). Add it to `.env`, or
pass as a `--env` flag below.

Register with Claude Code (uses an absolute path so it works regardless
of which directory `claude` is invoked from):

```bash
claude mcp add contextstore \
  --env CONTEXTSTORE_API_KEY=csk_live_... \
  -- /Users/pedropinto/graphstore/.venv/bin/contextstore-mcp
```

Or, for a team-shared setup checked into the repo, create `.mcp.json` in
the project root:

```json
{
  "mcpServers": {
    "contextstore": {
      "type": "stdio",
      "command": "/Users/pedropinto/graphstore/.venv/bin/contextstore-mcp",
      "env": {
        "CONTEXTSTORE_API_KEY": "csk_live_..."
      }
    }
  }
}
```

Verify it registered and connected:

```bash
claude mcp list   # should show "Connected" for contextstore
```

Then inside a Claude Code session, `/mcp` shows its tools, or just ask
Claude to remember or recall something.
