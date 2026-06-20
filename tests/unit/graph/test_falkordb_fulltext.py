"""Unit tests for FalkorDBGraphStore.find_by_fulltext and its query
sanitization, with the FalkorDB client mocked out (no real FalkorDB needed --
see tests/integration/test_falkordb_store.py for the live-server coverage).
"""

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from redis.exceptions import ResponseError

from contextstore.graph.falkordb_store import FalkorDBGraphStore, _sanitize_fulltext_query
from contextstore.models.provenance import Provenance
from contextstore.models.scope import Scope


def _node(entity_id, name: str, scope: Scope) -> MagicMock:
    node = MagicMock()
    node.properties = {
        "id": str(entity_id),
        "name": name,
        "entity_type": "thing",
        "scope_json": json.dumps(scope.to_query_dict()),
        "provenance_json": Provenance(source="test").model_dump_json(),
    }
    return node


def _store_with_fake_graph(fake_graph: MagicMock) -> FalkorDBGraphStore:
    store = FalkorDBGraphStore()
    store._graph_for = MagicMock(return_value=fake_graph)  # type: ignore[method-assign]
    return store


def test_sanitize_strips_redisearch_operators_and_or_joins_tokens():
    assert _sanitize_fulltext_query("RG-88") == "RG | 88"
    assert _sanitize_fulltext_query("Korrigan Cells Ltd") == "Korrigan | Cells | Ltd"
    assert _sanitize_fulltext_query("Recall R-2025-014") == "Recall | R | 2025 | 014"


def test_sanitize_special_characters_only_returns_empty_string():
    assert _sanitize_fulltext_query("()[]{}!@*") == ""
    assert _sanitize_fulltext_query("") == ""


async def test_find_by_fulltext_returns_ranked_entity_ids_in_score_order():
    scope = Scope.from_dict({"tenant_id": "t1"})
    entity_a, entity_b = uuid4(), uuid4()
    fake_graph = MagicMock()
    result = MagicMock()
    result.result_set = [
        [_node(entity_a, "RG-88", scope), 4.0],
        [_node(entity_b, "RG-88 Mark II", scope), 2.0],
    ]
    fake_graph.query = AsyncMock(return_value=result)
    store = _store_with_fake_graph(fake_graph)

    matches = await store.find_by_fulltext(scope, "RG-88", limit=5)

    assert matches == [(entity_a, 1), (entity_b, 2)]
    query_args = fake_graph.query.await_args.args
    assert query_args[1]["q"] == "RG | 88"
    assert query_args[1]["limit"] == 5


async def test_find_by_fulltext_query_sanitizing_to_nothing_skips_the_query():
    scope = Scope.from_dict({"tenant_id": "t1"})
    fake_graph = MagicMock()
    fake_graph.query = AsyncMock()
    store = _store_with_fake_graph(fake_graph)

    matches = await store.find_by_fulltext(scope, "()[]{}", limit=5)

    assert matches == []
    fake_graph.query.assert_not_called()


async def test_find_by_fulltext_missing_index_returns_empty_not_raise():
    scope = Scope.from_dict({"tenant_id": "t1"})
    fake_graph = MagicMock()
    fake_graph.query = AsyncMock(side_effect=ResponseError("Unknown index name"))
    store = _store_with_fake_graph(fake_graph)

    matches = await store.find_by_fulltext(scope, "anything", limit=5)

    assert matches == []


async def test_find_by_fulltext_filters_out_entities_outside_scope():
    scope_a = Scope.from_dict({"tenant_id": "t1", "user_id": "u1"})
    scope_b = Scope.from_dict({"tenant_id": "t1", "user_id": "u2"})
    entity_a, entity_b = uuid4(), uuid4()
    fake_graph = MagicMock()
    result = MagicMock()
    result.result_set = [
        [_node(entity_a, "Foo", scope_a), 2.0],
        [_node(entity_b, "Foo", scope_b), 2.0],
    ]
    fake_graph.query = AsyncMock(return_value=result)
    store = _store_with_fake_graph(fake_graph)

    matches = await store.find_by_fulltext(scope_a, "Foo", limit=5)

    assert matches == [(entity_a, 1)]
