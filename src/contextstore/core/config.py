"""Application configuration, loaded from environment variables / .env."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "production"] = "development"
    log_level: str = "INFO"

    # CORS allow-list as a comma-separated string (kept a plain str rather than
    # list[str] so a bare "a,b" env value parses without pydantic-settings'
    # JSON-decoding of complex types). Read via `allowed_origins_list`.
    allowed_origins: str = "http://localhost:3000"

    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_password: SecretStr | None = None

    anthropic_api_key: SecretStr
    openai_api_key: SecretStr

    # Postgres (Supabase) -- holds users/api_keys/usage_log for auth. Optional
    # so the app and the (graph-only) test suite still import cleanly without a
    # database; when unset, the auth pool is not created and the /v1/ routes
    # return 503 (auth unconfigured) rather than silently accepting requests.
    database_url: SecretStr | None = None
    # Bearer token guarding the operator-only /v1/keys management endpoints.
    # Optional at import time; the endpoints return 503 if it's unset.
    admin_token: SecretStr | None = None

    # Per-API-key rate limits (requests per minute), enforced in-process.
    rate_limit_recall: int = 60
    rate_limit_memories: int = 30

    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    extraction_model: str = "claude-haiku-4-5-20251001"
    # Query classifier's LLM fallback (core/classifier.py). Same model as
    # extraction, but a separate setting so the two LLM uses can be pointed
    # at different models and costed independently.
    classifier_model: str = "claude-haiku-4-5-20251001"
    # Recall synthesis (core/synthesiser.py). Same model as extraction and the
    # classifier, but a separate setting so the three LLM uses can be pointed at
    # different models and costed independently.
    synthesis_model: str = "claude-haiku-4-5-20251001"
    vector_merge_threshold: float = 0.92
    vector_candidate_threshold: float = 0.80

    @property
    def allowed_origins_list(self) -> list[str]:
        """`allowed_origins` split into a list of trimmed, non-empty origins."""
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
