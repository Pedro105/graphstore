"""FalkorDB implementation of the GraphStore interface.

Internal schema (reified-claim model): entities are nodes labeled `:Entity`;
facts are reified as `:Claim` nodes linked to their subject and object entities
by fixed `:SUBJECT` / `:OBJECT` edges -- `(:Claim)-[:SUBJECT]->(:Entity)` and
`(:Claim)-[:OBJECT]->(:Entity)`. The predicate is a property on the Claim node,
not the Cypher edge type, so (unlike the previous direct-edge model) nothing is
inlined into a query string -- all Cypher lives parameterized in graph/queries.py
and claim (de)serialization in graph/schema.py. A claim carries coherence state
(status active/superseded/disputed/retracted, validity, asserted_by, supersedes,
disputed_with); the write path adjudicates new assertions against existing active
claims (resolution/conflict_resolver.py) before upserting. `properties`, `scope`,
etc. are JSON-serialized into string properties because FalkorDB node/edge
properties must be scalars or arrays of scalars, not nested maps.

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

Fact identity / dedup is no longer a storage concern: corroboration and
conflict are decided by the adjudicator (resolution/conflict_resolver.py) and
expressed as claim status, not as edge MERGE. `core/service.py` still biases
extraction to reuse an existing tenant's predicate vocabulary (see
`find_predicates`/`extraction/extractor.py`) so the same conceptual fact picks
the same predicate and adjudication can match it.
"""

import json
import re
from typing import Any
from uuid import UUID

import structlog
from falkordb.asyncio import FalkorDB
from falkordb.asyncio.graph import AsyncGraph
from redis.exceptions import ResponseError

from contextstore.models.claim import Claim
from contextstore.models.entity import Entity
from contextstore.models.fact import Fact
from contextstore.models.fact_claim import FactClaim
from contextstore.models.memory import Memory
from contextstore.models.provenance import Provenance
from contextstore.models.relation import Relation
from contextstore.models.scope import Scope
from contextstore.graph import queries
from contextstore.graph.schema import claim_to_node_props, node_to_claim
from contextstore.graph.store import GraphStore
from contextstore.retrieval.traversal import breadth_first_traverse

logger = structlog.get_logger()

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
        "observed_types_json": json.dumps(entity.observed_types or [entity.entity_type]),
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
        # Legacy nodes written before observed_types existed fall back to the
        # single canonical type, so the field is always populated on read.
        observed_types=json.loads(
            properties.get("observed_types_json") or json.dumps([properties["entity_type"]])
        ),
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


def _claim_to_relation(claim: FactClaim) -> Relation:
    """Collapse a live FactClaim into a display-edge Relation (subject->object,
    raw predicate as relation_type). The single chokepoint where the reified
    claim model is turned back into a simple directed edge for callers."""
    asserter = claim.asserted_by[0] if claim.asserted_by else "unknown"
    provenance = Provenance(
        source=asserter,
        created_at=claim.valid_from,
        confidence=claim.confidence,
    )
    return Relation(
        id=claim.id,
        source_entity_id=claim.subject_id,
        target_entity_id=claim.object_id,
        relation_type=claim.raw_predicate,
        properties=claim.properties,
        scope=claim.scope,
        provenance=provenance,
        claims=claim.claims,
        contributing_sources=claim.asserted_by,
        status=claim.status,
        disputed_with=claim.disputed_with,
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
        """Persist the memory's entities only. Facts are written separately as
        adjudicated `:Claim` nodes via `upsert_claim` (see GraphStore)."""
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

        return memory_id

    async def find_active_claims(
        self, scope: Scope, subject_id: UUID, predicate: str
    ) -> list[FactClaim]:
        graph = self._graph_for(scope.tenant_id)
        try:
            result = await graph.query(
                queries.FIND_ACTIVE_CLAIMS,
                {"subject_id": str(subject_id), "predicate": predicate},
            )
        except ResponseError:
            return []
        claims = (node_to_claim(row[0].properties) for row in result.result_set)
        return [claim for claim in claims if scope.includes(claim.scope)]

    async def upsert_claim(self, claim: FactClaim, memory_id: str) -> None:
        graph = self._graph_for(claim.scope.tenant_id)
        await graph.query(
            queries.UPSERT_CLAIM,
            {
                "id": str(claim.id),
                "props": claim_to_node_props(claim, memory_id),
                "subject_id": str(claim.subject_id),
                "object_id": str(claim.object_id),
            },
        )

    async def project_display_edges(self, scope: Scope) -> list[Relation]:
        graph = self._graph_for(scope.tenant_id)
        try:
            result = await graph.query(queries.PROJECT_LIVE_CLAIMS)
        except ResponseError:
            return []
        relations: list[Relation] = []
        for row in result.result_set:
            claim = node_to_claim(row[0].properties)
            if not scope.includes(claim.scope):
                continue
            relations.append(_claim_to_relation(claim))
        return relations

    async def find_predicates(self, scope: Scope) -> list[str]:
        graph = self._graph_for(scope.tenant_id)
        try:
            result = await graph.query(queries.DISTINCT_PREDICATES)
        except ResponseError:
            return []
        return sorted({row[0] for row in result.result_set if row[0]})

    async def find_disputed_claims(self, scope: Scope) -> list[FactClaim]:
        graph = self._graph_for(scope.tenant_id)
        try:
            result = await graph.query(queries.DISPUTED_CLAIMS)
        except ResponseError:
            return []
        claims = (node_to_claim(row[0].properties) for row in result.result_set)
        return [claim for claim in claims if scope.includes(claim.scope)]

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

        async def fetch_neighbours(frontier_ids: list[str]) -> list[tuple[Entity, Relation]]:
            # One hop through live claims: a `:Claim` node is treated as a logical
            # edge between its subject and object, reachable from either endpoint
            # (so a fact surfaces from either side). Superseded/retracted claims
            # are excluded -- recall only traverses current truth. One query per
            # frontier; the BFS dedups and decides re-expansion (retrieval/
            # traversal.py).
            result = await graph.query(
                queries.FETCH_CLAIM_NEIGHBOURS,
                {"frontier_ids": frontier_ids},
            )
            pairs: list[tuple[Entity, Relation]] = []
            for row in result.result_set:
                neighbour = _node_to_entity(row[0].properties)
                if not scope.includes(neighbour.scope):
                    continue
                relation = _claim_to_relation(node_to_claim(row[1].properties))
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
            queries.DELETE_MEMORY_WITH_CLAIMS,
            {"memory_id": memory_id},
        )
        return bool(result.nodes_deleted > 0)

    async def delete_entity(self, entity_id: UUID, tenant_id: str) -> bool:
        graph = self._graph_for(tenant_id)
        result = await graph.query(queries.DELETE_ENTITY_WITH_CLAIMS, {"id": str(entity_id)})
        return bool(result.nodes_deleted > 0)

    async def graph_stats(self, tenant_id: str) -> tuple[int, int]:
        graph = self._graph_for(tenant_id)
        try:
            nodes = await graph.query(queries.COUNT_ENTITIES)
            edges = await graph.query(queries.COUNT_LIVE_CLAIMS)
        except ResponseError:
            # Graph key doesn't exist yet (nothing ever written for this tenant).
            return (0, 0)
        node_count = int(nodes.result_set[0][0]) if nodes.result_set else 0
        edge_count = int(edges.result_set[0][0]) if edges.result_set else 0
        return (node_count, edge_count)

    async def fetch_entity_claims_page(
        self, tenant_id: str, offset: int, limit: int
    ) -> tuple[list[Fact], int]:
        graph = self._graph_for(tenant_id)
        try:
            total_result = await graph.query("MATCH (n:Entity) RETURN count(n)")
        except ResponseError:
            # Graph key doesn't exist yet (nothing ever written for this tenant).
            return ([], 0)
        total = int(total_result.result_set[0][0]) if total_result.result_set else 0
        if total == 0:
            return ([], total)

        result = await graph.query(
            "MATCH (n:Entity) "
            "RETURN n.id, n.name, n.entity_type, n.claims_json "
            "ORDER BY n.id SKIP $offset LIMIT $limit",
            {"offset": int(offset), "limit": int(limit)},
        )

        facts: list[Fact] = []
        for node_id, name, entity_type, claims_json in result.result_set:
            claims = _claims_from_json(claims_json or "[]")
            superseded_ids = {
                UUID(claim_id)
                for claim in claims
                for claim_id in (claim.provenance.supersedes or [])
            }
            for claim in claims:
                facts.append(
                    Fact(
                        tenant_id=tenant_id,
                        entity_id=UUID(node_id),
                        entity_name=name,
                        entity_type=entity_type,
                        property_name=claim.property_name,
                        value=claim.value,
                        source=claim.provenance.source,
                        asserted_at=claim.provenance.created_at,
                        superseded=claim.id in superseded_ids,
                    )
                )
        return (facts, total)

    async def drop_graph(self, tenant_id: str) -> None:
        graph = self._graph_for(tenant_id)
        try:
            await graph.delete()
        except ResponseError as exc:
            # Dropping a graph that was never created is a no-op, not a failure.
            if "key doesn't exist" not in str(exc).lower() and "empty key" not in str(exc).lower():
                raise

    async def health_check(self) -> bool:
        try:
            return bool(await self._client.connection.ping())
        except Exception:
            return False

    async def aclose(self) -> None:
        await self._client.connection.aclose()
