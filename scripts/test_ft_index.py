"""Throwaway script: confirm FalkorDB full-text index behavior before writing
production code. Not part of the test suite -- run manually:

    uv run python scripts/test_ft_index.py

Answers:
  1. Index creation procedure + idempotency (does calling it twice error?)
  2. Does it need to be created before or after nodes exist?
  3. Does writing a node after the index exists get indexed automatically?
  4. Query procedure + ranking/score semantics
  5. Special-character query handling (what errors, what doesn't)
"""

import asyncio

from falkordb.asyncio import FalkorDB
from redis.exceptions import ResponseError


async def main() -> None:
    db = FalkorDB(host="localhost", port=6379)
    graph = db.select_graph("ft_test_scratch")

    print("=== 1. create index BEFORE any nodes exist ===")
    await graph.query("CALL db.idx.fulltext.createNodeIndex('Entity', 'name')")
    print("created ok")

    print("\n=== 2. idempotency: create the same index again ===")
    try:
        await graph.query("CALL db.idx.fulltext.createNodeIndex('Entity', 'name')")
        print("second create did NOT raise")
    except ResponseError as exc:
        print(f"second create raised: {exc}")

    print("\n=== 3. insert nodes AFTER index exists -- auto-indexed? ===")
    await graph.query(
        "CREATE (n:Entity {id: 'e1', name: 'RG-88 Battery Cell'}), "
        "(m:Entity {id: 'e2', name: 'Korrigan Cells Ltd'}), "
        "(o:Entity {id: 'e3', name: 'Recall R-2025-014'})"
    )
    result = await graph.query(
        "CALL db.idx.fulltext.queryNodes('Entity', 'RG-88') YIELD node, score "
        "RETURN node.id, node.name, score"
    )
    print("query for 'RG-88' immediately after insert:", result.result_set)

    print("\n=== 4. insert a node, THEN create index on a fresh label -- does it backfill? ===")
    await graph.query("CREATE (n:Backfill {id: 'b1', name: 'Backfill Target'})")
    await graph.query("CALL db.idx.fulltext.createNodeIndex('Backfill', 'name')")
    result = await graph.query(
        "CALL db.idx.fulltext.queryNodes('Backfill', 'Backfill') YIELD node, score "
        "RETURN node.id, score"
    )
    print("query immediately after index-after-insert:", result.result_set)

    print("\n=== 5. ranking semantics: multiple matches, what does score look like? ===")
    await graph.query(
        "CREATE (n:Entity {id: 'e4', name: 'RG-88 Mark II'}), (m:Entity {id: 'e5', name: 'RG-88'})"
    )
    result = await graph.query(
        "CALL db.idx.fulltext.queryNodes('Entity', 'RG-88') YIELD node, score "
        "RETURN node.id, node.name, score ORDER BY score DESC"
    )
    print("multi-match ranking:", result.result_set)

    print("\n=== 6. special RediSearch characters in query string ===")
    for bad_query in ["RG-88", "RG_88!", "Recall R-2025-014", "a-b*c@d", "()[]{}"]:
        try:
            result = await graph.query(
                "CALL db.idx.fulltext.queryNodes('Entity', $q) YIELD node, score RETURN node.id, score",
                {"q": bad_query},
            )
            print(f"  {bad_query!r}: ok, {len(result.result_set)} results")
        except ResponseError as exc:
            print(f"  {bad_query!r}: RAISED {exc}")

    print("\n=== 7. query against a label with no full-text index ===")
    try:
        result = await graph.query(
            "CALL db.idx.fulltext.queryNodes('NoSuchIndex', 'anything') YIELD node, score "
            "RETURN node, score"
        )
        print("no-index query did NOT raise:", result.result_set)
    except ResponseError as exc:
        print(f"no-index query RAISED: {exc}")

    print("\n=== cleanup ===")
    await db.connection.execute_command("GRAPH.DELETE", "ft_test_scratch")
    await db.connection.aclose()


if __name__ == "__main__":
    asyncio.run(main())
