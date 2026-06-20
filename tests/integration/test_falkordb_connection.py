"""Integration test verifying FalkorDB connectivity.

Requires a real FalkorDB instance (FALKORDB_HOST / FALKORDB_PORT). Skips
rather than fails if one isn't reachable, so this suite doesn't block
development on machines without FalkorDB running.
"""

import os

import pytest
from falkordb.asyncio import FalkorDB

TEST_GRAPH_NAME = "test_falkordb_connection"


@pytest.fixture
async def falkordb_client():
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))

    db = FalkorDB(host=host, port=port)
    try:
        await db.connection.ping()
    except Exception as exc:
        pytest.skip(f"FalkorDB not reachable at {host}:{port}: {exc}")

    yield db
    await db.connection.aclose()


@pytest.fixture
async def test_graph(falkordb_client):
    graph = falkordb_client.select_graph(TEST_GRAPH_NAME)
    yield graph
    if TEST_GRAPH_NAME in await falkordb_client.list_graphs():
        await graph.delete()


async def test_falkordb_connection_is_reachable(falkordb_client):
    assert await falkordb_client.connection.ping() is True


async def test_create_read_delete_node(falkordb_client, test_graph):
    await test_graph.query("CREATE (:SpikeCheck {label: $label})", {"label": "hello"})

    result = await test_graph.query("MATCH (n:SpikeCheck) RETURN n.label")
    (label,) = result.result_set[0]
    assert label == "hello"

    await test_graph.delete()

    assert TEST_GRAPH_NAME not in await falkordb_client.list_graphs()
