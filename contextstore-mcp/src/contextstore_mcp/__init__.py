"""contextstore-mcp: a standalone MCP server for ContextStore.

A thin HTTP client over the ContextStore API that exposes `remember` and
`recall` as MCP tools. It imports nothing from the ContextStore backend -- it
talks to the hosted API over HTTP with an API key, so it installs and runs on
its own via `uvx contextstore-mcp`.
"""
