"""MCP server configuration, loaded from environment variables / .env.

A thin HTTP client (see client.py) that never touches FalkorDB or an LLM
provider directly, so it needs only where the API is and the key to reach it --
no ANTHROPIC_API_KEY / FALKORDB_HOST / DATABASE_URL.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONTEXTSTORE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_url: str = "http://localhost:8000"
    # The ContextStore API key (csk_live_...). Sent as `Authorization: Bearer
    # <key>` on every backend call; the tenant is resolved from it server-side,
    # so this server never constructs or sends a tenant_id/scope itself.
    api_key: str


@lru_cache
def get_mcp_settings() -> MCPSettings:
    return MCPSettings()  # type: ignore[call-arg]
