"""FalkorDB implementation of the GraphStore interface.

Internal schema: entities are nodes labeled `:Entity`; relations are edges
whose Cypher type is the relation's `relation_type` (validated against
`_SAFE_IDENTIFIER`, since openCypher requires edge types to be inlined into
the query rather than passed as parameters). `properties`, `scope`, and
`provenance` are JSON-serialized into string properties because FalkorDB
node/edge properties must be scalars or arrays of scalars, not nested maps.

Tenant isolation: each tenant gets a structurally separate FalkorDB graph
(named `tenant_<tenant_id>`), selected via `_graph_for`. This is required
because FalkorDB vector search doesn't combine well with property filters
(confirmed against https://docs.falkordb.com/cypher/indexing/vector-index.html
and live-tested below) — filtering by tenant *after* an ANN search can't
guarantee a tenant gets any results back if other tenants' vectors dominate
the top-k window, so isolation has to be structural, not a WHERE clause.

Scope filtering on the *other* scope keys (user_id, project, etc.) is still
done in Python after a broader Cypher fetch within the tenant's graph,
since scope is stored as an opaque JSON blob — a deliberate simplification
for the foundation phase.

Embeddings must be written via the `vecf32()` function in a dedicated SET
clause — verified live that setting a plain list via `SET n += $props`
is silently invisible to the vector index, even though it round-trips fine
as an ordinary property.

FalkorDB's vector index returns a cosine *distance* (0 = identical, 1 =
unrelated), not similarity — verified live. `find_similar_entities`
converts this to similarity (`1 - distance`) before returning, so callers
and config thresholds (VECTOR_MERGE_THRESHOLD etc.) work in the usual
"higher = more similar" convention.

Relations are deduplicated at write time, keyed on (source_entity_id,
target_entity_id, relation_type) -- the relationship pattern itself, not
relation properties (see `_write_relation`). This is an exact string match
on relation_type, which is otherwise a free string from extraction; nothing
guarantees two `remember()` calls describing the same conceptual fact pick
the same relation_type, so `core/service.py` biases extraction to reuse an
existing tenant's relation_type vocabulary (see
`_existing_relation_types`/`extraction/extractor.py`) rather than relying on
the storage layer to reconcile synonyms after the fact. On a match,
properties/provenance/claims are merged via models/claim.py (not frozen);
`support_count` increments and `last_seen` updates; the matched edge's
original `id` is preserved.
"""

import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from falkordb.asyncio import FalkorDB
from falkordb.asyncio.graph import AsyncGraph
from redis.exceptions import ResponseError

from contextstore.models.claim import Claim, apply_claim, derive_active_view
from contextstore.models.entity import Entity
from contextstore.models.memory import Memory
from contextstore.models.provenance import Provenance
from contextstore.models.relation import Relation
from contextstore.models.scope import Scope
from contextstore.graph.store import GraphStore
from contextstore.retrieval.traversal import breadth_first_traverse

logger = structlog.get_logger()

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SAFE_TENANT_ID = re.compile(r"^[A-Za-z0-9_-]+$")

# RediSearch's query parser treats most punctuation as operators (notably
# `-` as NOT), so a raw entity name like "RG-88" parses as "RG AND NOT 88"
# and matches nothing even though the entity exists verbatim -- confirmed
# live against FalkorDB (scripts/test_ft_index.py). Stripping everything
# but alphanumerics down to whitespace-separated tokens, then OR-joining
# them with `|`, avoids the parser entirely and turns "any token matches"
# into the query semantics (RediSearch's default is AND across
# space-separated terms, which would otherwise require every word in a
# multi-word query to appear on the same entity name -- also verified live).
_FULLTEXT_TOKEN = re.compile(r"[A-Za-z0-9]+")


def _sanitize_fulltext_query(query_text: str) -> str:
    tokens = _FULLTEXT_TOKEN.findall(query_text)
    return " | ".join(tokens)


def _safe_relation_type(relation_type: str) -> str:
    if not _SAFE_IDENTIFIER.match(relation_type):
        raise ValueError(
            f"relation_type {relation_type!r} is not safe to use as a Cypher edge type "
            "(must match ^[A-Za-z_][A-Za-z0-9_]*$)"
        )
    return relation_type


def _safe_tenant_id(tenant_id: str) -> str:
    if not _SAFE_TENANT_ID.match(tenant_id):
        raise ValueError(
            f"tenant_id {tenant_id!r} is not safe to use as a FalkorDB graph name "
            "(must match ^[A-Za-z0-9_-]+$)"
        )
    return tenant_id


def _claims_to_json(claims: list[Claim]) -> str:
    return json.dumps([claim.model_dump(mode="json") for claim in claims])


def _claims_from_json(raw: str) -> list[Claim]:
    return [Claim.model_validate(item) for item in json.loads(raw)]


def _entity_to_node_props(entity: Entity, memory_id: str) -> dict[str, Any]:
    return {
        "name": entity.name,
        "entity_type": entity.entity_type,
        "properties_json": json.dumps(entity.properties),
        "scope_json": json.dumps(entity.scope.to_query_dict()),
        "provenance_json": entity.provenance.model_dump_json(),
        "merge_candidates_json": json.dumps([str(eid) for eid in entity.merge_candidates]),
        "claims_json": _claims_to_json(entity.claims),
        "contributing_sources_json": json.dumps(entity.contributing_sources),
        "memory_id": memory_id,
    }


def _node_to_entity(properties: dict[str, Any]) -> Entity:
    return Entity(
        id=UUID(properties["id"]),
        name=properties["name"],
        entity_type=properties["entity_type"],
        properties=json.loads(properties.get("properties_json", "{}")),
        scope=Scope.from_dict(json.loads(properties["scope_json"])),
        provenance=Provenance.model_validate_json(properties["provenance_json"]),
        embedding=properties.get("embedding"),
        merge_candidates=[
            UUID(eid) for eid in json.loads(properties.get("merge_candidates_json", "[]"))
        ],
        claims=_claims_from_json(properties.get("claims_json", "[]")),
        contributing_sources=json.loads(properties.get("contributing_sources_json", "[]")),
    )


def _relation_to_edge_props(relation: Relation, memory_id: str) -> dict[str, Any]:
    return {
        "id": str(relation.id),
        "source_entity_id": str(relation.source_entity_id),
        "target_entity_id": str(relation.target_entity_id),
        "properties_json": json.dumps(relation.properties),
        "scope_json": json.dumps(relation.scope.to_query_dict()),
        "provenance_json": relation.provenance.model_dump_json(),
        "claims_json": _claims_to_json(relation.claims),
        "contributing_sources_json": json.dumps(relation.contributing_sources),
        "memory_id": memory_id,
    }


def _edge_to_relation(relation_type: str, properties: dict[str, Any]) -> Relation:
    return Relation(
        id=UUID(properties["id"]),
        source_entity_id=UUID(properties["source_entity_id"]),
        target_entity_id=UUID(properties["target_entity_id"]),
        relation_type=relation_type,
        properties=json.loads(properties.get("properties_json", "{}")),
        scope=Scope.from_dict(json.loads(properties["scope_json"])),
        provenance=Provenance.model_validate_json(properties["provenance_json"]),
        claims=_claims_from_json(properties.get("claims_json", "[]")),
        contributing_sources=json.loads(properties.get("contributing_sources_json", "[]")),
    )


class FalkorDBGraphStore(GraphStore):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: str | None = None,
    ) -> None:
        self._client = FalkorDB(host=host, port=port, password=password)

    def _graph_for(self, tenant_id: str) -> AsyncGraph:
        graph_name = f"tenant_{_safe_tenant_id(tenant_id)}"
        graph: AsyncGraph = self._client.select_graph(graph_name)
        return graph

    async def ensure_graph_initialized(self, tenant_id: str, embedding_dimension: int) -> None:
        graph = self._graph_for(tenant_id)
        try:
            await graph.query(
                "CREATE VECTOR INDEX FOR (e:Entity) ON (e.embedding) "
                "OPTIONS {dimension: $dim, similarityFunction: $sim}",
                {"dim": embedding_dimension, "sim": "cosine"},
            )
        except ResponseError as exc:
            if "already indexed" not in str(exc):
                raise
        await self._ensure_ft_index(graph)

    async def _ensure_ft_index(self, graph: AsyncGraph) -> None:
        """Create the full-text index on Entity.name, idempotently.

        Safe to call on a graph that already has the index (idempotent --
        verified live, see scripts/test_ft_index.py) and on a graph that
        already has entities (FalkorDB backfills existing nodes into a
        newly created full-text index). New writes are indexed
        automatically -- no explicit update step needed after MERGE/SET,
        also verified live.
        """
        try:
            await graph.query("CALL db.idx.fulltext.createNodeIndex('Entity', 'name')")
        except ResponseError as exc:
            if "already indexed" not in str(exc):
                raise

    async def write_memory(self, memory: Memory) -> str:
        memory_id = str(memory.id)
        graph = self._graph_for(memory.scope.tenant_id)

        for entity in memory.entities:
            query = "MERGE (n:Entity {id: $id}) SET n += $props"
            params: dict[str, Any] = {
                "id": str(entity.id),
                "props": _entity_to_node_props(entity, memory_id),
            }
            if entity.embedding is not None:
                query += " SET n.embedding = vecf32($embedding)"
                params["embedding"] = entity.embedding
            await graph.query(query, params)

        for relation in memory.relations:
            await self._write_relation(graph, relation, memory_id)

        return memory_id

    async def _write_relation(self, graph: AsyncGraph, relation: Relation, memory_id: str) -> None:
        """Create a new edge, or fold this write's claim(s) into an existing
        one. Conflict/supersession rules live in models/claim.py -- this is
        the relation-side equivalent of resolution/entity_resolver.py's
        merge, just performed at write time (read-before-write) since
        relation dedup, unlike entity resolution, doesn't happen earlier in
        the pipeline.

        support_count/last_seen bookkeeping and the matched edge's original
        `id` are preserved exactly as before this change -- only
        properties/provenance/claims/contributing_sources are now updated
        on a match instead of frozen.
        """
        rel_type = _safe_relation_type(relation.relation_type)
        now = datetime.now(UTC).isoformat()
        source_id = str(relation.source_entity_id)
        target_id = str(relation.target_entity_id)

        existing = await graph.query(
            f"MATCH (a:Entity {{id: $source_id}})-[r:{rel_type}]->(b:Entity {{id: $target_id}}) "
            "RETURN r LIMIT 1",
            {"source_id": source_id, "target_id": target_id},
        )

        if existing.result_set:
            existing_props = existing.result_set[0][0].properties
            existing_claims = _claims_from_json(existing_props.get("claims_json", "[]"))
            claims = apply_claim(existing_claims, relation.provenance, relation.properties)
            properties, provenance, contributing_sources = derive_active_view(claims)
            merged = relation.model_copy(
                update={
                    "id": UUID(existing_props["id"]),
                    "properties": properties,
                    "provenance": provenance,
                    "claims": claims,
                    "contributing_sources": contributing_sources,
                }
            )
            update_props = _relation_to_edge_props(merged, memory_id)
            await graph.query(
                f"MATCH (a:Entity {{id: $source_id}})-[r:{rel_type}]->"
                f"(b:Entity {{id: $target_id}}) "
                "SET r += $props, r.support_count = r.support_count + 1, r.last_seen = $now",
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "props": update_props,
                    "now": now,
                },
            )
            return

        claims = apply_claim([], relation.provenance, relation.properties)
        properties, provenance, contributing_sources = derive_active_view(claims)
        created = relation.model_copy(
            update={
                "properties": properties,
                "provenance": provenance,
                "claims": claims,
                "contributing_sources": contributing_sources,
            }
        )
        create_props = _relation_to_edge_props(created, memory_id)
        create_props["support_count"] = 1
        create_props["last_seen"] = now
        await graph.query(
            f"MATCH (a:Entity {{id: $source_id}}), (b:Entity {{id: $target_id}}) "
            f"CREATE (a)-[r:{rel_type}]->(b) SET r += $props",
            {"source_id": source_id, "target_id": target_id, "props": create_props},
        )

    async def get_entity(self, entity_id: UUID, tenant_id: str) -> Entity | None:
        graph = self._graph_for(tenant_id)
        result = await graph.query(
            "MATCH (n:Entity {id: $id}) RETURN n LIMIT 1", {"id": str(entity_id)}
        )
        if not result.result_set:
            return None
        return _node_to_entity(result.result_set[0][0].properties)

    async def find_entities(
        self,
        scope: Scope,
        name: str | None = None,
        entity_type: str | None = None,
    ) -> list[Entity]:
        graph = self._graph_for(scope.tenant_id)
        result = await graph.query(
            "MATCH (n:Entity) "
            "WHERE ($name IS NULL OR n.name = $name) "
            "AND ($entity_type IS NULL OR n.entity_type = $entity_type) "
            "RETURN n",
            {"name": name, "entity_type": entity_type},
        )
        entities = (_node_to_entity(row[0].properties) for row in result.result_set)
        return [entity for entity in entities if scope.includes(entity.scope)]

    async def find_similar_entities(
        self,
        scope: Scope,
        embedding: list[float],
        entity_type: str | None,
        k: int,
    ) -> list[tuple[Entity, float]]:
        graph = self._graph_for(scope.tenant_id)
        try:
            result = await graph.query(
                "CALL db.idx.vector.queryNodes('Entity', 'embedding', $k, vecf32($embedding)) "
                "YIELD node, score RETURN node, score ORDER BY score ASC",
                {"k": k, "embedding": embedding},
            )
        except ResponseError as exc:
            if "undefined attribute" in str(exc):
                # No vector index yet for this tenant (nothing written, or
                # ensure_graph_initialized hasn't run) -- no matches.
                return []
            raise

        matches: list[tuple[Entity, float]] = []
        for node, distance in result.result_set:
            entity = _node_to_entity(node.properties)
            if entity_type is not None and entity.entity_type != entity_type:
                continue
            if not scope.includes(entity.scope):
                continue
            matches.append((entity, 1.0 - distance))
        return matches

    async def find_by_fulltext(
        self,
        scope: Scope,
        query_text: str,
        limit: int,
    ) -> list[tuple[UUID, int]]:
        sanitized = _sanitize_fulltext_query(query_text)
        if not sanitized:
            return []

        graph = self._graph_for(scope.tenant_id)
        try:
            result = await graph.query(
                "CALL db.idx.fulltext.queryNodes('Entity', $q) YIELD node, score "
                "RETURN node, score ORDER BY score DESC LIMIT $limit",
                {"q": sanitized, "limit": limit},
            )
        except ResponseError as exc:
            logger.warning(
                "find_by_fulltext.query_failed",
                tenant_id=scope.tenant_id,
                error=str(exc),
            )
            return []

        matches: list[tuple[UUID, int]] = []
        for node, _score in result.result_set:
            entity = _node_to_entity(node.properties)
            if not scope.includes(entity.scope):
                continue
            matches.append((entity.id, len(matches) + 1))
        return matches

    async def traverse(
        self,
        start_entity_ids: list[UUID],
        max_depth: int,
        scope: Scope,
    ) -> list[tuple[Entity, list[Relation]]]:
        if max_depth < 1:
            raise ValueError("max_depth must be >= 1")

        graph = self._graph_for(scope.tenant_id)
        query = (
            "MATCH (start:Entity) WHERE start.id IN $start_ids "
            f"MATCH path = (start)-[*1..{int(max_depth)}]-(end:Entity) "
            "WHERE end.id <> start.id "
            "RETURN end, relationships(path)"
        )
        result = await graph.query(query, {"start_ids": [str(eid) for eid in start_entity_ids]})

        entities_by_id: dict[UUID, Entity] = {}
        relations_by_entity: dict[UUID, dict[UUID, Relation]] = {}

        for end_node, edges in result.result_set:
            entity = _node_to_entity(end_node.properties)
            if not scope.includes(entity.scope):
                continue
            entities_by_id[entity.id] = entity
            relations = relations_by_entity.setdefault(entity.id, {})
            for edge in edges:
                relation = _edge_to_relation(edge.relation, edge.properties)
                relations[relation.id] = relation

        return [
            (entity, list(relations_by_entity[entity_id].values()))
            for entity_id, entity in entities_by_id.items()
        ]

    async def traverse_from_seeds(
        self,
        scope: Scope,
        seed_ids: list[str],
        depth: int,
        max_entities: int = 200,
    ) -> tuple[list[Entity], list[Relation], bool]:
        """Iterative BFS expansion -- one batched Cypher query per hop. The
        BFS bookkeeping (frontier/visited/cap/relation filter) lives in
        retrieval/traversal.py; this method only supplies the two
        Cypher-backed fetchers and the tenant's graph.
        """
        graph = self._graph_for(scope.tenant_id)

        async def fetch_seeds(ids: list[str]) -> list[Entity]:
            result = await graph.query(
                "MATCH (e:Entity) WHERE e.id IN $ids RETURN e",
                {"ids": ids},
            )
            entities = (_node_to_entity(row[0].properties) for row in result.result_set)
            return [entity for entity in entities if scope.includes(entity.scope)]

        async def fetch_neighbours(
            frontier_ids: list[str], visited_ids: list[str]
        ) -> list[tuple[Entity, Relation]]:
            # Undirected: matches the one-hop `traverse` convention so a fact
            # is reachable from either endpoint. One query for the whole
            # frontier, not one per node.
            result = await graph.query(
                "MATCH (e:Entity)-[r]-(neighbour:Entity) "
                "WHERE e.id IN $frontier_ids AND NOT neighbour.id IN $visited_ids "
                "RETURN neighbour, r",
                {"frontier_ids": frontier_ids, "visited_ids": visited_ids},
            )
            pairs: list[tuple[Entity, Relation]] = []
            for neighbour_node, edge in result.result_set:
                neighbour = _node_to_entity(neighbour_node.properties)
                if not scope.includes(neighbour.scope):
                    continue
                relation = _edge_to_relation(edge.relation, edge.properties)
                pairs.append((neighbour, relation))
            return pairs

        return await breadth_first_traverse(
            seed_ids,
            depth,
            max_entities,
            fetch_seeds,
            fetch_neighbours,
            tenant_id=scope.tenant_id,
        )

    async def delete_memory(self, memory_id: str, tenant_id: str) -> bool:
        graph = self._graph_for(tenant_id)
        result = await graph.query(
            "MATCH (n:Entity {memory_id: $memory_id}) DETACH DELETE n",
            {"memory_id": memory_id},
        )
        return bool(result.nodes_deleted > 0)

    async def health_check(self) -> bool:
        try:
            return bool(await self._client.connection.ping())
        except Exception:
            return False

    async def aclose(self) -> None:
        await self._client.connection.aclose()
