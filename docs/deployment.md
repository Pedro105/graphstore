# Deployment (Fly.io)

How the ContextStore **backend** is containerized and deployed to Fly.io, and
how the self-hosted **FalkorDB** instance it depends on is run. Supabase
(Postgres) is already hosted and is not managed here. The frontend stays local
for now (separate future task).

## Topology

Two Fly apps in the same region (`lhr`, nearest Fly region to the Supabase
project in AWS `eu-west-1`/Ireland), plus the already-hosted Supabase:

```
                 public internet (HTTPS)
                          │
                 ┌────────▼─────────┐        private 6PN         ┌──────────────────────┐
   frontend ───▶ │ contextstore-api │ ─────────────────────────▶ │ contextstore-falkordb │
   (local now)   │  FastAPI (8000)  │   .internal:6379 (auth)    │  FalkorDB + volume    │
                 └────────┬─────────┘                            └──────────────────────┘
                          │ TLS
                 ┌────────▼─────────┐
                 │ Supabase Postgres │  (already hosted, AWS eu-west-1)
                 └──────────────────┘
```

FalkorDB has **no public service** — it's reachable only over Fly's private
WireGuard mesh (6PN) at `contextstore-falkordb.internal:6379`, authenticated
with a password. The graph never touches the public internet.

## FalkorDB hosting decision: self-hosted on Fly.io

We self-host FalkorDB as a second Fly app with a persistent volume, rather than
using **FalkorDB Cloud** (managed, Startup tier ~$73/mo, 12-hour automated
backups). Reasoning for this stage (solo dev, pre-product demo):

| Factor | Self-host on Fly (chosen) | FalkorDB Cloud Startup |
| --- | --- | --- |
| Cost | ~$5–10/mo (1× shared-cpu-1x + 1 GB volume) | $73/mo |
| Latency (hot path) | Sub-ms, same-region private 6PN | Cross-cloud hop Fly→AWS on every recall |
| Backups | Fly automatic **daily** volume snapshots (5-day retention) | Managed, every 12h |
| Persistence | AOF + RDB on a single, un-replicated volume | Managed, durable |
| Ops | One `fly volumes create` + tiny config | Zero |

The decisive trade-offs: it's ~10× cheaper and meaningfully lower-latency on the
hot path (every `recall` makes several FalkorDB round trips: vector seed →
multi-hop BFS). The backup downside is acceptable here because the graph data is
**regenerable** via `scripts/populate_graph.py`, and Fly's daily snapshots give
a floor.

**Revisit FalkorDB Cloud** when the store holds real, non-regenerable customer
data — at that point managed 12h backups and a durable, replicated store are
worth $73/mo. The app depends only on the abstract `GraphStore` interface and
`FALKORDB_HOST`/`PORT`/`PASSWORD`, so switching is a secrets change, not a code
change.

## Prerequisites

```bash
# Install + authenticate the Fly CLI (the auth step is interactive).
brew install flyctl
fly auth login
```

All commands below are run from the **repo root** (the Docker build context must
see `pyproject.toml` / `uv.lock` / `src/`).

## One-time setup

### 1. Create the apps

```bash
fly apps create contextstore-falkordb
fly apps create contextstore-api
```

### 2. FalkorDB: volume + secret + deploy

```bash
# Persistent volume for AOF/RDB files (mounted at /data per fly.falkordb.toml).
fly volumes create falkordb_data --region lhr --size 1 -a contextstore-falkordb

# Password + persistence flags. REDIS_ARGS is a secret so the password is never
# committed. Generate a strong password, e.g. `openssl rand -hex 24`.
#
# The bind MUST include `::` -- Fly's private network is IPv6-only, so a Redis
# bound to 0.0.0.0 (IPv4) alone refuses all 6PN connections (see Troubleshooting).
fly secrets set -a contextstore-falkordb \
  REDIS_ARGS="--requirepass <FALKORDB_PASSWORD> --appendonly yes --appendfsync everysec --bind 0.0.0.0 ::"

fly deploy --config deploy/fly.falkordb.toml

# Keep exactly one machine (a single volume can't be shared across machines).
fly scale count 1 -a contextstore-falkordb
```

### 3. Backend: secrets + deploy

Set every secret with `fly secrets set` — **none of these go in git or fly.toml.**
Use the same `<FALKORDB_PASSWORD>` as in step 2.

```bash
fly secrets set -a contextstore-api \
  ANTHROPIC_API_KEY="sk-ant-..." \
  OPENAI_API_KEY="sk-..." \
  DATABASE_URL="postgresql://postgres:<PW>@db.<PROJECT>.supabase.co:5432/postgres" \
  ADMIN_TOKEN="<openssl rand -hex 32>" \
  FALKORDB_PASSWORD="<FALKORDB_PASSWORD>"

fly deploy --config deploy/fly.toml
```

Non-secret config (`FALKORDB_HOST`, `FALKORDB_PORT`, `ALLOWED_ORIGINS`,
`ENVIRONMENT`, `LOG_LEVEL`) lives in `[env]` in `deploy/fly.toml`.

### 4. Confirm Postgres / migrations

The Supabase instance already has `001_initial.sql` and `002_agents.sql` applied
(from the auth task) — no new migration here. Confirm the deployed backend
reaches the same instance:

```bash
# The /health endpoint reports Postgres reachability (see below).
# Directly verify the schema is present if needed:
psql "$DATABASE_URL" -c "\dt"   # expect: users, api_keys, usage_log, agents
```

## Health checks

`GET /health` (unauthenticated) is the Fly health-check target. It returns
`200` only when **both** FalkorDB and Postgres are reachable, `503` otherwise:

```json
{"status":"ok","version":"0.1.0","checks":{"falkordb":"ok","postgres":"ok"}}
```

A `503` pulls the machine out of rotation / triggers a restart. (`GET /ready`
remains a FalkorDB-only readiness probe.)

## Smoke test (against the live URL)

```bash
API=https://contextstore-api.fly.dev

# 1. Both dependencies up
curl -s $API/health        # expect 200, falkordb + postgres "ok"

# 2. Mint / reuse an API key (admin-token protected; reuse an existing one if you have it)
curl -s -X POST $API/v1/keys \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"user_id":"<uuid>","tenant_id":"demo","name":"smoke"}'
KEY=csk_live_...   # from the response

# 3. Write a memory
curl -s -X POST $API/v1/memories \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"content":"Ada works at Acme on the billing service.","source":"smoke"}'

# 4. Recall with synthesis — confirm RetrievalStats populate
curl -s -X POST $API/v1/recall \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"query":"Where does Ada work?","synthesise":true}' | jq '.synthesis, .stats'
```

Optionally run the eval against `$API` as a heavier smoke test (do not modify
the eval dataset).

## Cold start / `min_machines_running`

`deploy/fly.toml` sets `auto_stop_machines = "off"` and
`min_machines_running = 1`, so **one machine stays warm 24/7** — no cold start
on a demo. The first request after a scale-to-zero would otherwise pay a cold
start of container pull + Python import + eager FalkorDB connect (the app
connects to FalkorDB during startup, so a cold start also waits on FalkorDB).

Trade-off: a warm `shared-cpu-1x`/512 MB machine costs roughly **$2–4/mo** even
when idle. For a product demo that's worth it. To save cost on a purely
personal/dev deploy, set `auto_stop_machines = "stop"` and
`min_machines_running = 0` and accept a few seconds of cold start on the first
hit.

## Redeploy

```bash
fly deploy --config deploy/fly.toml             # backend
fly deploy --config deploy/fly.falkordb.toml    # FalkorDB (rarely needed)
```

Code or `[env]`/`fly.toml` changes ship via `fly deploy`. Secret changes
(`fly secrets set`) trigger a rolling restart automatically.

## Logs

```bash
fly logs -a contextstore-api          # backend (structured JSON in prod)
fly logs -a contextstore-falkordb     # FalkorDB
fly status -a contextstore-api        # machine/health overview
```

## Rollback

Fly keeps previous releases. To roll back a bad backend deploy:

```bash
fly releases -a contextstore-api               # list versions
fly deploy -a contextstore-api --image <previous-image-ref>
# or roll back to the immediately prior release:
fly releases rollback -a contextstore-api
```

A bad secret change can be reverted with another `fly secrets set` (or
`fly secrets unset`), which also triggers a restart. FalkorDB data persists
across deploys/rollbacks on the volume; a rollback of the *backend* does not
touch graph data.

## Point the local frontend at the deployed backend (verification only)

Temporary check that the deployed backend serves the frontend end to end — not
a permanent switch (frontend hosting is a separate task):

```bash
# frontend/.env.local
CONTEXTSTORE_API_URL=https://contextstore-api.fly.dev
```

Run the memories page, confirm a recall works through the deployed backend, then
**revert** `CONTEXTSTORE_API_URL` to `http://localhost:8000` for local dev. The
backend's `ALLOWED_ORIGINS` must include the frontend origin (it includes
`http://localhost:3000` by default; add the production frontend URL there when
it ships).

## Troubleshooting

**Backend crash-loops with `Connection refused` on `contextstore-falkordb.internal:6379`.**
FalkorDB is listening on IPv4 only. Fly's 6PN private network is **IPv6-only** and
`.internal` names resolve to AAAA records, so a Redis bound to `0.0.0.0` (IPv4
wildcard) refuses every private-network connection. Fix: the `REDIS_ARGS` secret
must bind the IPv6 wildcard too — `--bind 0.0.0.0 ::`. Diagnose from inside the
FalkorDB machine:

```bash
fly ssh console -a contextstore-falkordb -C "redis-cli ping"                 # NOAUTH => requirepass is active (good)
fly ssh console -a contextstore-falkordb -C "redis-cli -h fly-local-6pn ping"  # Connection refused => NOT listening on IPv6 (the bug)
```

After fixing `REDIS_ARGS` and redeploying FalkorDB, the second command should
return `NOAUTH` (reachable over 6PN). Then restart the backend so it reconnects.

**A Next.js dev server is running inside the FalkorDB machine.** That's the
**FalkorDB Browser** (a Next.js UI on :3000) bundled in the full
`falkordb/falkordb` image — not a misdeploy. We use `falkordb/falkordb-server`
(server-only, port 6379, no browser) in production to avoid it.

## Secrets — never committed

Real secrets live only in `fly secrets` (production) and `.env` (gitignored,
local). `.env.example` holds placeholders only. The full secret set:

| Secret | App | Notes |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | api | extraction / classifier / synthesis |
| `OPENAI_API_KEY` | api | embeddings |
| `DATABASE_URL` | api | Supabase asyncpg DSN (auth) |
| `ADMIN_TOKEN` | api | guards `/v1/keys` |
| `FALKORDB_PASSWORD` | api | must equal FalkorDB's `--requirepass` |
| `REDIS_ARGS` | falkordb | contains `--requirepass <pw>` + persistence flags |
