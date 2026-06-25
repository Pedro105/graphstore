"""Thin async HTTP client wrapping the ContextStore API.

Calls the hosted ContextStore API over HTTP with a Bearer API key; the backend
resolves the tenant from the key, so this client never constructs or sends a
tenant_id/scope itself. It imports nothing from the backend -- only the minimal
response models in models.py.
"""

from typing import Any

import httpx

from contextstore_mcp.models import Conflict, RecallResult, RememberResult


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
    ) -> RememberResult:
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
        return RememberResult.model_validate(response.json())

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

    async def inspect_conflicts(self) -> list[Conflict]:
        response = await self._client.get("/v1/conflicts", headers=self._headers())
        response.raise_for_status()
        return [Conflict.model_validate(item) for item in response.json()]

    async def aclose(self) -> None:
        await self._client.aclose()
