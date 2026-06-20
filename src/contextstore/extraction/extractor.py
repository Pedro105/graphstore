"""LLM-based entity/relation extraction via Instructor + Anthropic."""

import anthropic
import instructor

from contextstore.core.config import get_settings
from contextstore.extraction.prompts import EXTRACTION_SYSTEM_PROMPT
from contextstore.extraction.schemas import ExtractedEntity, ExtractedRelation, ExtractionResult


def _build_user_message(content: str, existing_relation_types: list[str] | None) -> str:
    """Bias extraction toward reusing an existing relation_type for the same
    conceptual fact, rather than inventing a new-but-synonymous string on
    every write.

    Why this exists: relation deduplication (graph/falkordb_store.py) keys
    on an exact relation_type string match, because Cypher edge types must
    be inlined rather than parameterized. relation_type is otherwise a free
    string (extraction/schemas.py), so nothing previously stopped the model
    from extracting "owns" one call and "relates_to" another for what's
    really an update to the same relationship -- the second write then
    silently created a parallel edge instead of updating the first (see the
    eval harness's globex_current_price_single_hop case). Telling the model
    what's already in the graph lets it make the same call a human curator
    would: reuse the existing string for an update to the same kind of
    relationship, but still mint a new one when the text genuinely
    describes something different. Tenant-wide rather than entity-pair-
    specific, since which pair is involved isn't known until after this
    same extraction call resolves entity names.
    """
    if not existing_relation_types:
        return content
    types_list = ", ".join(sorted(existing_relation_types))
    context = (
        f"Relation types already used elsewhere in this knowledge graph: {types_list}.\n"
        "If the text below describes an update to a relationship that already exists "
        "between the same two entities (e.g. a revised price, a changed status), reuse "
        "the EXACT existing relation_type string rather than inventing a new but "
        "similar one. Only use a different relation_type if the text describes a "
        "genuinely different kind of relationship.\n\n---\n\n"
    )
    return context + content


def _total_tokens(completion: object) -> int:
    """Total (input + output) tokens from a raw Anthropic completion, or 0 if
    usage isn't present. Defensive: the value feeds usage accounting only, so a
    missing/oddly-shaped usage object must never break extraction."""
    usage = getattr(completion, "usage", None)
    if usage is None:
        return 0
    return int(getattr(usage, "input_tokens", 0) or 0) + int(
        getattr(usage, "output_tokens", 0) or 0
    )


async def extract(
    content: str, existing_relation_types: list[str] | None = None
) -> tuple[list[ExtractedEntity], list[ExtractedRelation], int]:
    """Extract entities and relations from `content`, returning them plus the
    total tokens the extraction LLM call consumed (for usage accounting). The
    token count is surfaced here rather than swallowed so the write path can log
    it; it does not affect extraction behaviour."""
    settings = get_settings()
    client = instructor.from_anthropic(
        anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
    )

    result, completion = await client.chat.completions.create_with_completion(
        model=settings.extraction_model,
        max_tokens=4096,
        system=EXTRACTION_SYSTEM_PROMPT,
        response_model=ExtractionResult,
        messages=[
            {"role": "user", "content": _build_user_message(content, existing_relation_types)}
        ],
    )

    return result.entities, result.relations, _total_tokens(completion)
