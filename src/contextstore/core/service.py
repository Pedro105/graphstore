"""Orchestration: the write path (remember) and read path (recall).

remember(): extract -> resolve each entity -> map relations -> attach
provenance -> write. recall(): classify the query for routing (unless the
caller pinned it) -> seed (vector, full-text, or both fused via RRF) ->
traverse -> assemble.
"""

import asyncio
import re
import time
from uuid import UUID

import structlog

from contextstore.core.classifier import QueryClassifier
from contextstore.core.config import get_settings
from contextstore.extraction.extractor import extract
from contextstore.graph.store import GraphStore
from contextstore.models.classification import ClassifierResult
from contextstore.models.entity import Entity
from contextstore.models.memory import Memory
from contextstore.models.provenance import Provenance
from contextstore.models.recall import RecallResult, RetrievalMode, RetrievalStats
from contextstore.models.relation import Relation
from contextstore.models.scope import Scope
from contextstore.core.synthesiser import RecallSynthesiser
from contextstore.resolution.entity_resolver import resolve_entity
from contextstore.retrieval.fusion import reciprocal_rank_fusion
from contextstore.vector.embeddings import EmbeddingProvider

logger = structlog.get_logger()

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9_]+")


async def _existing_relation_types(scope: Scope, graph_store: GraphStore) -> list[str]:
    """Distinct relation_type strings already used in this tenant's graph,
    passed into extract() so it's biased toward reusing one instead of
    inventing a synonym for the same conceptual fact (see
    extraction/extractor.py's _build_user_message for why).

    Built from the same two GraphStore methods api/routes.py's GET /v1/graph
    already composes (find_entities + a 1-hop traverse from every entity)
    -- no new GraphStore method needed. Cost: one full-tenant read on every
    remember() call, scaling with tenant size. Fine at demo scale; would
    need caching or a dedicated index at a much larger one.
    """
    entities = await graph_store.find_entities(scope)
    if not entities:
        return []
    traversal_results = await graph_store.traverse([entity.id for entity in entities], 1, scope)
    return sorted(
        {relation.relation_type for _, relations in traversal_results for relation in relations}
    )


def _normalize_relation_type(relation_type: str) -> str:
    """Coerce LLM-produced relation types into a safe Cypher edge type.

    Real LLM output doesn't always match the prompt's snake_case
    suggestions exactly (e.g. "works at" with a space), so this is applied
    before building a Relation rather than trusting extraction verbatim.
    """
    normalized = _UNSAFE_CHARS.sub("_", relation_type.strip().lower()).strip("_")
    if not normalized:
        return "relates_to"
    if not (normalized[0].isalpha() or normalized[0] == "_"):
        normalized = f"rel_{normalized}"
    return normalized


async def remember(
    content: str,
    scope: Scope,
    source: str,
    graph_store: GraphStore,
    embedding_provider: EmbeddingProvider,
    confidence: float = 1.0,
    evidence: list[str] | None = None,
) -> tuple[Memory, int]:
    """Extract -> resolve -> write one memory. Returns the persisted Memory and
    the number of tokens the extraction LLM call consumed (surfaced for usage
    accounting at the API boundary; 0 if the provider reported none)."""
    settings = get_settings()
    await graph_store.ensure_graph_initialized(scope.tenant_id, settings.embedding_dimension)

    existing_relation_types = await _existing_relation_types(scope, graph_store)
    extracted_entities, extracted_relations, tokens_used = await extract(
        content, existing_relation_types
    )
    provenance = Provenance(source=source, confidence=confidence, evidence=evidence)

    resolved_by_name: dict[str, Entity] = {}
    for extracted_entity in extracted_entities:
        resolved_by_name[extracted_entity.name] = await resolve_entity(
            extracted_entity, scope, provenance, graph_store, embedding_provider
        )

    relations: list[Relation] = []
    for extracted_relation in extracted_relations:
        source_entity = resolved_by_name.get(extracted_relation.source_name)
        target_entity = resolved_by_name.get(extracted_relation.target_name)
        if source_entity is None or target_entity is None:
            logger.warning(
                "remember.skipped_relation_unknown_entity",
                source_name=extracted_relation.source_name,
                target_name=extracted_relation.target_name,
            )
            continue
        relations.append(
            Relation(
                source_entity_id=source_entity.id,
                target_entity_id=target_entity.id,
                relation_type=_normalize_relation_type(extracted_relation.relation_type),
                properties=extracted_relation.properties,
                scope=scope,
                provenance=provenance,
            )
        )

    memory = Memory(
        content=content,
        entities=list(resolved_by_name.values()),
        relations=relations,
        scope=scope,
        provenance=provenance,
    )
    await graph_store.write_memory(memory)
    return memory, tokens_used


async def _seed_entities(
    query: str,
    scope: Scope,
    graph_store: GraphStore,
    embedding_provider: EmbeddingProvider,
    limit: int,
    retrieval_mode: RetrievalMode,
) -> list[Entity]:
    """Seed step: vector similarity, full-text keyword search, or both
    fused via reciprocal rank fusion (retrieval/fusion.py). `vector` and
    `fulltext` skip the other method (and RRF) entirely; `hybrid` (the
    default) runs both and fuses.

    `find_by_fulltext` returns bare entity ids, not Entity objects (see
    graph/store.py), so fulltext-only matches need a `get_entity` lookup
    to be resolved into the Entity this function must return.
    """
    vector_seeds: list[tuple[Entity, float]] = []
    fulltext_ranked: list[tuple[UUID, int]] = []

    if retrieval_mode in ("vector", "hybrid"):
        embedding = await embedding_provider.embed(query)
        vector_seeds = await graph_store.find_similar_entities(scope, embedding, None, limit)

    if retrieval_mode in ("fulltext", "hybrid"):
        fulltext_ranked = await graph_store.find_by_fulltext(scope, query, limit)

    if retrieval_mode == "vector":
        return [entity for entity, _ in vector_seeds]

    if retrieval_mode == "fulltext":
        fetched = await asyncio.gather(
            *(
                graph_store.get_entity(entity_id, scope.tenant_id)
                for entity_id, _ in fulltext_ranked
            )
        )
        return [entity for entity in fetched if entity is not None]

    vector_ranked = [(entity.id, rank) for rank, (entity, _) in enumerate(vector_seeds, start=1)]
    fused = reciprocal_rank_fusion(vector_ranked, fulltext_ranked)
    top_ids = [entity_id for entity_id, _ in fused[:limit]]

    entities_by_id = {entity.id: entity for entity, _ in vector_seeds}
    missing_ids = [entity_id for entity_id in top_ids if entity_id not in entities_by_id]
    if missing_ids:
        fetched = await asyncio.gather(
            *(graph_store.get_entity(entity_id, scope.tenant_id) for entity_id in missing_ids)
        )
        for entity_id, entity in zip(missing_ids, fetched, strict=True):
            if entity is not None:
                entities_by_id[entity_id] = entity

    return [entities_by_id[entity_id] for entity_id in top_ids if entity_id in entities_by_id]


async def _resolve_strategy(
    query: str,
    traversal_depth: int | None,
    retrieval_mode: RetrievalMode | None,
    classifier: QueryClassifier | None,
) -> tuple[RetrievalMode, int, ClassifierResult | None]:
    """Decide the effective (retrieval_mode, traversal_depth) for this recall.

    Caller-supplied params always win: if the caller pinned *either* knob,
    we skip the classifier entirely and fill any unspecified knob from the
    documented static defaults (hybrid / depth 1) -- this is the behaviour
    callers and the eval harness relied on before the classifier existed.
    Only when the caller left both unspecified do we classify the query and
    take the routing from its strategy, returning the ClassifierResult so
    recall() can surface it on the response.
    """
    if traversal_depth is not None or retrieval_mode is not None:
        return retrieval_mode or "hybrid", traversal_depth or 1, None

    classifier = classifier or QueryClassifier()
    result = await classifier.classify(query)
    logger.debug(
        "recall.classified",
        query=query,
        query_class=result.query_class,
        confidence=result.confidence,
        used_llm=result.used_llm,
    )
    return result.strategy.retrieval_mode, result.strategy.traversal_depth, result


async def recall(
    query: str,
    scope: Scope,
    graph_store: GraphStore,
    embedding_provider: EmbeddingProvider,
    limit: int = 10,
    traversal_depth: int | None = None,
    retrieval_mode: RetrievalMode | None = None,
    classifier: QueryClassifier | None = None,
    max_entities: int = 200,
    synthesise: bool = False,
    synthesiser: RecallSynthesiser | None = None,
) -> RecallResult:
    """classify (if unrouted) -> seed (bounded by `limit`) -> multi-hop
    BFS traverse -> assemble -> (optionally) synthesise.

    `traversal_depth` and `retrieval_mode` default to None, meaning "let the
    query classifier choose" (see `_resolve_strategy`). Passing either one
    explicitly pins routing and skips the classifier. `classifier` is
    injectable for testing; a default QueryClassifier is built only when
    classification actually runs.

    `limit` is the maximum number of seed entities returned from the seed
    step (see `_seed_entities` -- vector similarity, full-text, or both
    fused via RRF, depending on `retrieval_mode`). Traversal results from
    those seeds are not subject to this limit -- the returned RecallResult
    can contain more than `limit` entities once multi-hop neighbours are
    included. `max_entities` caps the total subgraph size returned from
    traversal; hitting it sets RecallResult.truncated.

    When `synthesise` is True, a natural-language answer is generated from the
    assembled subgraph and attached as RecallResult.synthesis (additive -- the
    structured entities/relations are always returned regardless). `synthesiser`
    is injectable for testing; a default RecallSynthesiser is built only when
    synthesis actually runs. Synthesis is best-effort: if it raises, the error
    is logged and the structured result is returned cleanly with synthesis=None,
    never surfaced to the caller as a recall failure.
    """
    # perf_counter (monotonic, sub-ms) -- the start mark sits before any work,
    # including classification and embedding, so retrieval_ms below covers the
    # whole start->traversal-complete span.
    start = time.perf_counter()

    effective_mode, effective_depth, classifier_result = await _resolve_strategy(
        query, traversal_depth, retrieval_mode, classifier
    )

    seed_entities = await _seed_entities(
        query, scope, graph_store, embedding_provider, limit, effective_mode
    )

    # Preserve the seed Entity objects (they carry the embedding vector from
    # the seed step); traverse_from_seeds re-fetches seeds too, but setdefault
    # below keeps the originals and overlays only the newly reached entities.
    entities_by_id: dict[UUID, Entity] = {entity.id: entity for entity in seed_entities}
    relations_by_id: dict[UUID, Relation] = {}
    truncated = False

    if seed_entities:
        reached_entities, reached_relations, truncated = await graph_store.traverse_from_seeds(
            scope,
            [str(entity.id) for entity in seed_entities],
            effective_depth,
            max_entities,
        )
        for entity in reached_entities:
            entities_by_id.setdefault(entity.id, entity)
        for relation in reached_relations:
            relations_by_id[relation.id] = relation
        if truncated:
            logger.warning(
                "recall.traversal_truncated",
                tenant_id=scope.tenant_id,
                query=query,
                depth=effective_depth,
                entity_count=len(entities_by_id),
                max_entities=max_entities,
            )

    # limit bounds the seed step only (passed as `k`/`limit` into
    # _seed_entities above). Once seeded, traversal neighbours are kept in
    # full -- re-slicing the merged seeds+traversal dict here would
    # silently discard exactly the graph-hop results GraphRAG exists to
    # surface (see Anomaly 4).
    entities = list(entities_by_id.values())
    included_ids = {entity.id for entity in entities}
    relations = [
        relation
        for relation in relations_by_id.values()
        if relation.source_entity_id in included_ids and relation.target_entity_id in included_ids
    ]

    # Traversal + assembly complete: everything after this point is synthesis
    # (optional) and result construction, excluded from retrieval_ms.
    retrieval_end = time.perf_counter()

    stats = RetrievalStats(
        total_ms=0.0,  # finalised after synthesis below
        retrieval_ms=(retrieval_end - start) * 1000,
        synthesis_ms=None,
        seeds_found=len(seed_entities),
        nodes_traversed=len(entities),
        relations_found=len(relations),
        depth_reached=effective_depth,
        # No classifier_result means routing was pinned by the caller (manual).
        query_class=classifier_result.query_class if classifier_result else "manual",
        used_llm_classifier=classifier_result.used_llm if classifier_result else False,
    )

    result = RecallResult(
        query=query,
        scope=scope,
        entities=entities,
        relations=relations,
        classifier_result=classifier_result,
        truncated=truncated,
        stats=stats,
    )

    if synthesise:
        try:
            result.synthesis = await (synthesiser or RecallSynthesiser()).synthesise(
                query, result, scope
            )
        except Exception:
            # Best-effort: a synthesis failure (Haiku call error, Instructor
            # parse error, ...) must not fail the recall. Keep the structured
            # result, leave synthesis=None.
            logger.exception("recall.synthesis_failed", tenant_id=scope.tenant_id, query=query)
        # synthesis_ms reflects time spent on the synthesis attempt, whether or
        # not it succeeded; it stays None only when synthesis was not requested.
        result.stats.synthesis_ms = (time.perf_counter() - retrieval_end) * 1000

    result.stats.total_ms = (time.perf_counter() - start) * 1000
    return result
