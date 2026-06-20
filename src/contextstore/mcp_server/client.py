"""Thin async HTTP client wrapping the ContextStore API.

Deliberately calls the running FastAPI server over HTTP rather than
importing core.service directly -- this is the same shape the production
MCP server will have once this is hosted and callers connect over HTTPS
with an API key. There's no auth yet, so `api_key` stays unset and no
Authorization header is sent; passing a real key later is the only change
needed (see `_headers`), not a rewrite.
"""

from typing import Any

import httpx

from contextstore.models.memory import Memory
from contextstore.models.recall import RecallResult


class ContextStoreClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=timeout, transport=transport
        )

    def _headers(self) -> dict[str, str]:
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}

    async def remember(
        self,
        content: str,
        source: str,
        extra_scope: dict[str, Any] | None = None,
        confidence: float = 1.0,
        evidence: list[str] | None = None,
    ) -> Memory:
        response = await self._client.post(
            "/v1/memories",
            json={
                "content": content,
                "source": source,
                "extra_scope": extra_scope or {},
                "confidence": confidence,
                "evidence": evidence,
            },
            headers=self._headers(),
        )
        response.raise_for_status()
        return Memory.model_validate(response.json())

    async def recall(
        self,
        query: str,
        extra_scope: dict[str, Any] | None = None,
        limit: int = 10,
        traversal_depth: int = 1,
        synthesise: bool = False,
    ) -> RecallResult:
        response = await self._client.post(
            "/v1/recall",
            json={
                "query": query,
                "extra_scope": extra_scope or {},
                "limit": limit,
                "traversal_depth": traversal_depth,
                "synthesise": synthesise,
            },
            headers=self._headers(),
        )
        response.raise_for_status()
        return RecallResult.model_validate(response.json())

    async def aclose(self) -> None:
        await self._client.aclose()
