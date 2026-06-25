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

# Type is a *soft* signal, not a partition (see resolve_entity). A different
# entity_type shaves a little off the vector score for the merge/candidate
# decision -- enough to prefer a same-type match on a tie, not enough to block
# merging a clearly-the-same entity that two agents typed differently. Small by
# design: the exact-name fast path (which now crosses types) is what actually
# fixes the duplicate-entity symptom; this only nudges the fuzzy vector path.
_TYPE_MISMATCH_PENALTY = 0.05


def _normalize_name(name: str) -> str:
    """Identity key for catching trivial surface variants of one name.

    Vector similarity alone is too brittle to dedup these: 'Ada Lovelace' vs
    'Ada lovelace' embeds at only ~0.90 cosine with text-embedding-3-small --
    below the 0.92 merge threshold -- so a one-letter case change would
    otherwise spawn a duplicate entity, the exact failure entity resolution
    exists to prevent. Collapsing case and surrounding/repeated whitespace
    lets an exact name match force a merge regardless of the vector score.
    """
    return " ".join(name.split()).casefold()


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
    # Embed on the name alone, not "{type}: {name}". Baking the type into the
    # embedding pushed surface-identical entities of different types far apart
    # ("Organization: Acme" vs "Product: Acme" embed at ~0.85), so the same
    # real-world thing forked into two nodes. Name-only keeps them vector-near,
    # and type is reconciled below rather than partitioned on.
    embedding = await embedding_provider.embed(extracted.name)

    # Pass entity_type=None: the store no longer discards cross-type candidates
    # for resolution. Type handling is the resolver's job now (soft penalty +
    # exact-name fast path below), so candidates of every type are considered.
    candidates = await graph_store.find_similar_entities(
        scope, embedding, None, _CANDIDATE_SEARCH_K
    )

    merge_candidates = []
    if candidates:
        # Exact-identity fast path: a candidate whose name matches (modulo
        # case/whitespace) is the same entity, so merge into it regardless of
        # vector score *or type*. This now crosses entity types: "Acme" the
        # Organization and "Acme" the Product resolve to one node. This is what
        # makes surface-form variants of one name reliably dedup even when their
        # embeddings fall just short of the merge threshold (see _normalize_name).
        normalized = _normalize_name(extracted.name)
        for candidate_entity, _score in candidates:
            if _normalize_name(candidate_entity.name) == normalized:
                return _merge_into_entity(
                    candidate_entity, provenance, extracted.properties, extracted.entity_type
                )

        # Fuzzy vector path: trust find_similar_entities' best-first ordering
        # (take the top candidate), but shave a small penalty off its score when
        # the type differs, so type stays a tiebreaker rather than a hard gate.
        best_entity, best_score = candidates[0]
        adjusted_score = _type_adjusted_score(best_entity, best_score, extracted.entity_type)
        if adjusted_score >= settings.vector_merge_threshold:
            return _merge_into_entity(
                best_entity, provenance, extracted.properties, extracted.entity_type
            )
        if adjusted_score >= settings.vector_candidate_threshold:
            merge_candidates = [best_entity.id]

    claims = apply_claim([], provenance, extracted.properties)
    properties, active_provenance, contributing_sources = derive_active_view(claims)
    return Entity(
        name=extracted.name,
        entity_type=extracted.entity_type,
        observed_types=[extracted.entity_type],
        properties=properties,
        scope=scope,
        provenance=active_provenance,
        embedding=embedding,
        merge_candidates=merge_candidates,
        claims=claims,
        contributing_sources=contributing_sources,
    )


def _type_adjusted_score(entity: Entity, score: float, extracted_type: str) -> float:
    """Vector score with a small penalty when the extracted type isn't one this
    entity has already been observed as -- type as a soft signal, not a filter."""
    observed = entity.observed_types or [entity.entity_type]
    if extracted_type in observed:
        return score
    return score - _TYPE_MISMATCH_PENALTY


def _merge_into_entity(
    entity: Entity, provenance: Provenance, properties: dict[str, Any], new_type: str
) -> Entity:
    """Fold this write's claim(s) into an existing entity rather than
    discarding them -- see models/claim.py for the conflict/supersession
    rules. Identity fields (id/name/entity_type/embedding/merge_candidates)
    are left untouched; `new_type` is unioned into `observed_types` so a
    type disagreement between writers is recorded, not used to fork the node.
    """
    claims = apply_claim(entity.claims, provenance, properties)
    merged_properties, active_provenance, contributing_sources = derive_active_view(claims)
    observed = entity.observed_types or [entity.entity_type]
    observed_types = observed if new_type in observed else [*observed, new_type]
    return entity.model_copy(
        update={
            "properties": merged_properties,
            "provenance": active_provenance,
            "claims": claims,
            "contributing_sources": contributing_sources,
            "observed_types": observed_types,
        }
    )
