# contextstore-mcp

An [MCP](https://modelcontextprotocol.io) server for
[ContextStore](https://graphdb.mintlify.app) — it gives Claude Code, Claude
Desktop, and Cursor two native tools:

- **`contextstore_remember`** — store a fact, decision, or observation in
  long-term memory.
- **`contextstore_recall`** — search that memory and get a grounded,
  natural-language answer back.

It's a thin HTTP client over the hosted ContextStore API, so it installs and
runs standalone — no FalkorDB, FastAPI, or model SDKs required.

## Install & run

Zero-install via [`uvx`](https://docs.astral.sh/uv/):

```bash
CONTEXTSTORE_API_KEY=csk_live_... uvx contextstore-mcp
```

## Configuration

Two environment variables (read from the environment or a local `.env`):

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `CONTEXTSTORE_API_KEY` | yes | — | Your API key (`csk_live_…`). The tenant/project is resolved from it server-side. |
| `CONTEXTSTORE_API_URL` | no | `http://localhost:8000` | Base URL of the ContextStore API. Point it at your deployment. |

## Use in Claude Desktop / Claude Code

Add to your MCP config (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "contextstore": {
      "command": "uvx",
      "args": ["contextstore-mcp"],
      "env": {
        "CONTEXTSTORE_API_KEY": "csk_live_your_key_here",
        "CONTEXTSTORE_API_URL": "https://contextstore-api.fly.dev"
      }
    }
  }
}
```

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy src
```
