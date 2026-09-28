# ContextStore (graphstore)

**A GraphRAG knowledge layer for multi-writer agents** — not chatbot memory,
but workflow-shaped memory where multiple agents write structured knowledge
to a shared graph with entity resolution, conflict adjudication, and
provenance on every fact.

## Status

Personal research / portfolio project. Business exploration paused. **The
hosted Fly.io backend may be offline** — run locally to explore (see
[Local setup](#local-setup) below).

## Skills demonstrated

- **Reified claim schema**: Facts stored as first-class `:Claim` nodes with
  provenance, validity windows, and conflict state — not inlined edge
  properties.
- **Unstructured→graph ETL**: LLM-powered extraction (Claude Haiku) turns
  natural language into entities and typed relations.
- **Entity resolution**: Embedding similarity + property matching merges
  "Pedro Costa" and "P. Costa" onto one shared entity across independent
  writes.
- **Conflict adjudication**: When agents contradict each other, claims enter
  a `disputed` state for explicit resolution rather than silent overwrites.
- **Hybrid GraphRAG recall**: Vector seed retrieval followed by graph
  traversal surfaces connected context that pure similarity search misses.
- **Eval harness**: Ground-truth dataset with entity presence, property value,
  and relation value checks — prevents silent regressions.
- **MCP tools**: Claude Code/Desktop integration via a standalone
  `uvx`-installable MCP server exposing `remember`/`recall`.

## Architecture

FastAPI backend, FalkorDB graph store with native vector index, Postgres for
auth/billing metadata. See [`docs/architecture.md`](docs/architecture.md) for
the full design and [`docs/decisions/`](docs/decisions/) for ADRs.

### Graph model (reified claims)

Claims are reified as `:Claim` nodes linked to subject/object entities via
`:SUBJECT` / `:OBJECT` edges. The predicate is a node property, not an edge
type — this allows coherence state (status, validity, provenance,
supersession, disputes) to live on the fact itself:

```
(:Entity)<-[:SUBJECT]-(:Claim {
    predicate: "supplies",
    status: "active" | "superseded" | "disputed" | "retracted",
    asserted_by: ["crm-agent", "supplier-agent"],
    valid_from: datetime,
    valid_to: datetime | null,
    supersedes: [claim_id, ...],
    disputed_with: [claim_id, ...]
})-[:OBJECT]->(:Entity)
```

Multiple agents can assert the same fact (corroboration increments
`support_count`), contradict each other (mutual `disputed_with` links), or
supersede prior facts (new claim's `supersedes` + old claim's
`valid_to`/`status`).

## Local setup

### Prerequisites

- Docker (for FalkorDB)
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and pnpm (for frontend)
- An Anthropic API key (for LLM extraction)

### Backend

```bash
# Start FalkorDB
docker run -p 6379:6379 -p 3000:3000 falkordb/falkordb:latest

# From repo root
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY at minimum

uv sync
uv run uvicorn contextstore.api.app:app --reload
```

Verify:

```bash
curl localhost:8000/health
curl localhost:8000/ready
```

### Frontend

```bash
cd frontend
cp .env.example .env.local
pnpm install
pnpm dev
```

Opens at `http://localhost:3000`.

### Import your chats (local)

Turn your ChatGPT or Claude conversation history into a searchable knowledge graph:

**Via the dashboard:**

1. Open `http://localhost:3000/dashboard/import`
2. Upload your export file or paste the JSON/transcript directly
3. View the extracted entities in Memories

**Via the API:**

```bash
# Import ChatGPT export (conversations.json)
curl -X POST localhost:8000/v1/imports/chats \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"content": "<paste-json-here>"}'

# Or upload a file
curl -X POST localhost:8000/v1/imports/chats/upload \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@path/to/conversations.json"
```

**Supported formats:**

- **ChatGPT**: Export from Settings → Data Controls → Export data (use `conversations.json`)
- **Claude**: JSON export of conversation history
- **Text transcript**: Markdown with `User:` / `Assistant:` prefixes

Sample files are in `examples/chats/` for testing.

### MCP server (Claude Code / Claude Desktop)

The MCP server is a standalone package in `contextstore-mcp/` that calls the
backend over HTTP:

```bash
claude mcp add contextstore \
  --env CONTEXTSTORE_API_KEY=csk_live_... \
  --env CONTEXTSTORE_API_URL=http://localhost:8000 \
  -- uvx contextstore-mcp
```

See [`contextstore-mcp/README.md`](contextstore-mcp/README.md) for full
configuration.

## Demo: coherence and disputes

The memories page (`/dashboard/memories`) visualizes the entity graph with
disputed edges highlighted. Ingest contradictory facts from different agents
to see disputes surface:

```bash
# Agent A says price is $10
curl -X POST localhost:8000/v1/memories \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"content":"Acme quoted $10/unit for Product Y","source":"supplier-agent"}'

# Agent B says price is $12
curl -X POST localhost:8000/v1/memories \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"content":"Acme is charging $12/unit for Product Y","source":"pricing-agent"}'
```

The graph UI shows the conflicting claims with their `disputed` status.

## Eval harness

```bash
# Run against local backend
uv run python eval/run_eval.py

# Against a different backend/tenant
uv run python eval/run_eval.py \
  --base-url http://localhost:8000 \
  --tenant-id contextstore_demo
```

Reports are written to `eval/reports/`. See [`eval/README.md`](eval/README.md)
for adding test cases and interpretation.

## What's here vs. what's not

### What's here

- Core API: `remember()`, `recall()`, entity graph inspection
- LLM extraction with entity resolution and conflict adjudication
- Hybrid vector + graph retrieval
- Multi-tenant isolation (graph-per-tenant)
- MCP server for Claude integration
- Eval harness with ground-truth checks
- Next.js frontend with graph visualization
- Fly.io + Cloudflare deployment configs (`deploy/`, `docs/deployment.md`)

### What's not here

- **No AWS Step Functions / Pulumi** — deployment is Fly.io + Cloudflare
- **No billing product** — auth/keys exist for API access, but there's no
  payment integration
- **No always-on hosted demo** — the Fly.io backend may be offline; run
  locally

## License

[MIT](LICENSE)
