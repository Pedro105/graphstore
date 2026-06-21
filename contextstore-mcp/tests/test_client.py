"""Unit tests for ContextStoreClient -- request shape only, HTTP fully mocked.

The mocked responses include extra fields the real API returns (scope,
provenance history, stats, ...) to prove the minimal response models ignore
them rather than failing to parse.
"""

import json

import httpx
import pytest

from contextstore_mcp.client import ContextStoreClient

REMEMBER_RESPONSE = {
    "id": "11111111-1111-1111-1111-111111111111",
    "content": "Pedro works at Acme.",
    "entities": [
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "name": "Pedro",
            "entity_type": "person",
            # Extra fields the real API returns -- must be ignored:
            "scope": {"tenant_id": "acme"},
            "provenance": {"source": "mcp", "confidence": 1.0},
            "claims": [],
        }
    ],
    "relations": [],
    "scope": {"tenant_id": "acme"},
    "provenance": {"source": "mcp", "confidence": 1.0},
}

RECALL_RESPONSE = {
    "query": "who is Pedro",
    "scope": {"tenant_id": "acme"},
    "entities": [
        {"id": "22222222-2222-2222-2222-222222222222", "name": "Pedro", "entity_type": "person"}
    ],
    "relations": [],
    "stats": {"total_ms": 1.0},  # extra, ignored
}


def make_client(
    captured_requests: list[httpx.Request],
    response_body: dict,
    status_code: int = 200,
    api_key: str | None = None,
) -> ContextStoreClient:
    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(status_code, json=response_body)

    return ContextStoreClient(
        base_url="http://testserver",
        api_key=api_key,
        transport=httpx.MockTransport(handler),
    )


async def test_remember_posts_to_correct_path_with_correct_body():
    captured: list[httpx.Request] = []
    client = make_client(captured, REMEMBER_RESPONSE)

    result = await client.remember(
        content="Pedro works at Acme.",
        source="mcp",
        extra_scope={"user_id": "u1"},
    )

    assert len(captured) == 1
    request = captured[0]
    assert request.method == "POST"
    assert request.url.path == "/v1/memories"
    body = json.loads(request.content)
    # No tenant_id/scope -- the body carries only non-tenant scope keys; tenant
    # is derived server-side from the API key.
    assert body == {
        "content": "Pedro works at Acme.",
        "source": "mcp",
        "extra_scope": {"user_id": "u1"},
        "confidence": 1.0,
        "evidence": None,
    }
    # The rich response parsed down to the fields we read; extras ignored.
    assert [e.name for e in result.entities] == ["Pedro"]
    assert result.entities[0].entity_type == "person"


async def test_remember_passes_confidence_and_evidence():
    captured: list[httpx.Request] = []
    client = make_client(captured, REMEMBER_RESPONSE)

    await client.remember(content="x", source="mcp", confidence=0.7, evidence=["doc_1"])

    body = json.loads(captured[0].content)
    assert body["confidence"] == 0.7
    assert body["evidence"] == ["doc_1"]


async def test_recall_posts_to_correct_path_with_correct_body():
    captured: list[httpx.Request] = []
    client = make_client(captured, RECALL_RESPONSE)

    result = await client.recall(query="who is Pedro")

    assert len(captured) == 1
    request = captured[0]
    assert request.method == "POST"
    assert request.url.path == "/v1/recall"
    body = json.loads(request.content)
    assert body == {
        "query": "who is Pedro",
        "extra_scope": {},
        "limit": 10,
        "traversal_depth": 1,
        "synthesise": False,
    }
    assert [e.name for e in result.entities] == ["Pedro"]


async def test_recall_passes_limit_and_traversal_depth():
    captured: list[httpx.Request] = []
    client = make_client(captured, RECALL_RESPONSE)

    await client.recall(query="x", limit=5, traversal_depth=2)

    body = json.loads(captured[0].content)
    assert body["limit"] == 5
    assert body["traversal_depth"] == 2


async def test_recall_passes_synthesise_flag():
    captured: list[httpx.Request] = []
    client = make_client(captured, RECALL_RESPONSE)

    await client.recall(query="x", synthesise=True)

    body = json.loads(captured[0].content)
    assert body["synthesise"] is True


async def test_no_authorization_header_when_no_api_key():
    captured: list[httpx.Request] = []
    client = make_client(captured, REMEMBER_RESPONSE)

    await client.remember(content="x", source="mcp")

    assert "authorization" not in captured[0].headers


async def test_authorization_header_present_when_api_key_set():
    captured: list[httpx.Request] = []
    client = make_client(captured, REMEMBER_RESPONSE, api_key="secret123")

    await client.remember(content="x", source="mcp")

    assert captured[0].headers["authorization"] == "Bearer secret123"


async def test_raises_on_http_error_status():
    captured: list[httpx.Request] = []
    client = make_client(captured, {"detail": "server error"}, status_code=500)

    with pytest.raises(httpx.HTTPStatusError):
        await client.remember(content="x", source="mcp")
