"""Tests for the MCP server: it starts (tools register) and formats output.

CONTEXTSTORE_API_KEY is set before importing the server because the module
builds its settings + client at import time -- the same shape it runs in for
real, so importing it here is itself a smoke test that it starts cleanly with
only the two env vars set.
"""

import os
from unittest.mock import AsyncMock

os.environ.setdefault("CONTEXTSTORE_API_KEY", "test-key")

from contextstore_mcp import server  # noqa: E402
from contextstore_mcp.models import (  # noqa: E402
    Entity,
    Provenance,
    RecallResult,
    Relation,
    RememberResult,
    Synthesis,
)


def test_format_remember_with_entities():
    memory = RememberResult(entities=[Entity(name="Pedro", entity_type="person")])
    assert server._format_remember_result(memory) == "Stored. Extracted entities: Pedro (person)."


def test_format_remember_with_no_entities():
    assert (
        server._format_remember_result(RememberResult(entities=[]))
        == "Stored, but no entities were extracted from this content."
    )


def test_format_recall_prefers_synthesis():
    result = RecallResult(synthesis=Synthesis(answer="Pedro works at Acme."))
    assert server._format_recall_result(result) == "Pedro works at Acme."


def test_format_recall_synthesis_with_caveat():
    result = RecallResult(synthesis=Synthesis(answer="Likely yes.", caveat="based on one source"))
    assert server._format_recall_result(result) == "Likely yes.\n\n(Caveat: based on one source)"


def test_format_recall_falls_back_to_structured_summary():
    e1 = Entity(id="22222222-2222-2222-2222-222222222222", name="Pedro", entity_type="person")
    e2 = Entity(id="33333333-3333-3333-3333-333333333333", name="Acme", entity_type="org")
    result = RecallResult(
        entities=[e1, e2],
        relations=[
            Relation(
                source_entity_id=e1.id,  # type: ignore[arg-type]
                target_entity_id=e2.id,  # type: ignore[arg-type]
                relation_type="works_at",
                provenance=Provenance(source="mcp", confidence=0.9),
            )
        ],
    )
    out = server._format_recall_result(result)
    assert "Pedro (person)" in out
    assert "Pedro --[works_at]--> Acme" in out
    assert "confidence: 0.90" in out


def test_format_recall_empty():
    assert server._format_recall_result(RecallResult()) == "No relevant memories found."


async def test_tools_are_registered():
    tools = await server.mcp.list_tools()
    names = {t.name for t in tools}
    assert {"contextstore_remember", "contextstore_recall"} <= names


async def test_remember_tool_calls_client_and_formats(monkeypatch):
    fake = AsyncMock(return_value=RememberResult(entities=[Entity(name="Acme", entity_type="org")]))
    monkeypatch.setattr(server.client, "remember", fake)

    out = await server.contextstore_remember("Acme is a customer.")

    assert out == "Stored. Extracted entities: Acme (org)."
    assert fake.await_args.kwargs["source"] == "mcp"


async def test_recall_tool_defaults_to_synthesise_true(monkeypatch):
    fake = AsyncMock(return_value=RecallResult(synthesis=Synthesis(answer="An answer.")))
    monkeypatch.setattr(server.client, "recall", fake)

    out = await server.contextstore_recall("a question")

    assert out == "An answer."
    # Behavior contract: the recall tool always requests synthesis.
    assert fake.await_args.kwargs["synthesise"] is True
