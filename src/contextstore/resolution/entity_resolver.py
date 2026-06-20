"""Vector-similarity entity resolution: decide whether an extracted entity is
an existing one, a likely-duplicate candidate, or genuinely new.
"""

from typing import Any

from contextstore.core.config import get_settings
from contextstore.extraction.schemas import ExtractedEntity
from contextstore.graph.store import GraphStore
from contextstore.models.claim import apply_claim, derive_active_view
from contextstore.models.entity import Entity
from contextstore.models.provenance import Provenance
from contextstore.models.scope import Scope
from contextstore.vector.embeddings import EmbeddingProvider

# Cushion above 1 (we only need the single best match) so a same-type match
# isn't missed just because a few closer-but-wrong-type neighbors come first.
_CANDIDATE_SEARCH_K = 5


async def resolve_entity(
    extracted: ExtractedEntity,
    scope: Scope,
    provenance: Provenance,
    graph_store: GraphStore,
    embedding_provider: EmbeddingProvider,
) -> Entity:
    """Resolve an extracted entity against existing entities in `scope`'s tenant.

    `provenance` is required to construct a new Entity (the model has no
    default) when no sufficiently-similar existing entity is reused as-is;
    it's not part of the resolution decision itself.
    """
    settings = get_settings()
    embedding = await embedding_provider.embed(f"{extracted.entity_type}: {extracted.name}")

    candidates = await graph_store.find_similar_entities(
        scope, embedding, extracted.entity_type, _CANDIDATE_SEARCH_K
    )

    merge_candidates = []
    if candidates:
        best_entity, best_score = candidates[0]
        if best_score >= settings.vector_merge_threshold:
            return _merge_into_entity(best_entity, provenance, extracted.properties)
        if best_score >= settings.vector_candidate_threshold:
            merge_candidates = [best_entity.id]

    claims = apply_claim([], provenance, extracted.properties)
    properties, active_provenance, contributing_sources = derive_active_view(claims)
    return Entity(
        name=extracted.name,
        entity_type=extracted.entity_type,
        properties=properties,
        scope=scope,
        provenance=active_provenance,
        embedding=embedding,
        merge_candidates=merge_candidates,
        claims=claims,
        contributing_sources=contributing_sources,
    )


def _merge_into_entity(
    entity: Entity, provenance: Provenance, properties: dict[str, Any]
) -> Entity:
    """Fold this write's claim(s) into an existing entity rather than
    discarding them -- see models/claim.py for the conflict/supersession
    rules. Identity fields (id/name/entity_type/embedding/merge_candidates)
    are left untouched; only the claim-derived view changes.
    """
    claims = apply_claim(entity.claims, provenance, properties)
    merged_properties, active_provenance, contributing_sources = derive_active_view(claims)
    return entity.model_copy(
        update={
            "properties": merged_properties,
            "provenance": active_provenance,
            "claims": claims,
            "contributing_sources": contributing_sources,
        }
    )
