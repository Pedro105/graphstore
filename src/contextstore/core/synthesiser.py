"""Recall synthesis: turn a structured RecallResult into a prose answer
grounded strictly in the retrieved subgraph.

Optional and additive -- only runs when recall() is called with
synthesise=True, and never replaces the structured entities/relations (see
models/recall.py's RecallResult.synthesis). Haiku 4.5 via Instructor, mirroring
the client/response_model pattern in extraction/extractor.py and
core/classifier.py.

The subgraph is serialised into a compact text representation (not raw JSON,
not a full Pydantic dump) by `serialise_subgraph` -- a pure, independently
testable function. Active claim values are surfaced as current facts; where a
property's history shows a superseded claim with a different value, the
conflict is surfaced explicitly so the model can flag it rather than silently
present a stale value as current.
"""

from collections import defaultdict
from typing import Any
from uuid import UUID

import anthropic
import instructor
import structlog

from contextstore.core.config import get_settings
from contextstore.models.claim import Claim, derive_active_view
from contextstore.models.entity import Entity
from contextstore.models.recall import RecallResult
from contextstore.models.relation import Relation
from contextstore.models.scope import Scope
from contextstore.models.synthesis import SynthesisResult

logger = structlog.get_logger()


SYNTHESIS_SYSTEM_PROMPT = """\
You are a synthesis step in a knowledge-graph memory system. You are given a \
user's QUERY and the ENTITIES and RELATIONS that were retrieved from the graph \
for it. Write a concise, direct prose answer to the query.

Strict rules:
- Use ONLY the facts in the provided ENTITIES and RELATIONS. Do not use outside \
knowledge, and do not infer facts that the graph does not state. If the \
retrieved facts do not answer the query, say so.
- Populate `grounded_entity_ids` with the exact bracketed entity ids (the \
`[...]` value on each entity line) of every entity your answer draws on.
- Set `confidence`:
  - "high" when the retrieved facts directly and completely answer the query.
  - "medium" or "low" when the answer is partial -- e.g. the graph contains one \
step of a multi-step chain but not the connecting fact. Explain what is missing \
in `caveat`.
  - "insufficient_data" when the retrieved subgraph contains nothing that \
answers the query. Do NOT invent an answer; state in `caveat` that the graph \
lacks the relevant information.
- Provenance: each fact lists the sources that asserted it. Attribute a fact to \
its source in the prose only where it adds meaning (e.g. "According to \
agent_quality, ..."), not on every sentence. When a fact line shows a \
`conflict` (different sources asserted different values), note the conflict in \
the answer or `caveat` rather than silently picking one value.
- Only state the active (current) value of a fact as current. A value marked \
`superseded` is historical -- never present it as the current fact.
- Always populate `caveat` when confidence is "medium", "low", or \
"insufficient_data", or when an answer rests on a conflict. Leave it null only \
for a clean, complete, high-confidence answer.\
"""


def _summarise_claims(
    claims: list[Claim], fallback_properties: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Return (active property values, conflict notes) for one entity/relation.

    Active values come from the claim history's latest-wins view
    (derive_active_view). A conflict note is emitted for any property whose
    history contains a superseded claim with a value different from the active
    one -- this is the seam that lets the prompt flag "source A says X, source
    B (superseded) said Y" instead of silently presenting only X.

    Falls back to `fallback_properties` when there is no claim history (which
    shouldn't happen for graph-written entities, but keeps this robust for
    hand-built RecallResults).
    """
    if not claims:
        return dict(fallback_properties), []

    active_props, _, _ = derive_active_view(claims)

    superseded_ids = {
        UUID(claim_id) for claim in claims for claim_id in (claim.provenance.supersedes or [])
    }
    claims_by_property: dict[str, list[Claim]] = defaultdict(list)
    for claim in claims:
        if claim.property_name is not None:
            claims_by_property[claim.property_name].append(claim)

    conflicts: list[str] = []
    for property_name, property_claims in sorted(claims_by_property.items()):
        active_value = active_props.get(property_name)
        differing = [
            claim
            for claim in property_claims
            if claim.id in superseded_ids and claim.value != active_value
        ]
        if not differing:
            continue
        non_superseded = [c for c in property_claims if c.id not in superseded_ids]
        active_source = (
            max(non_superseded, key=lambda c: c.provenance.created_at).provenance.source
            if non_superseded
            else "unknown"
        )
        prior = "; ".join(
            f"{claim.value!r} (source {claim.provenance.source})" for claim in differing
        )
        conflicts.append(
            f"conflict on {property_name}: active={active_value!r} "
            f"(source {active_source}); superseded {prior}"
        )

    return active_props, conflicts


def _format_properties(properties: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value!r}" for key, value in sorted(properties.items()))


def _entity_lines(entity: Entity) -> list[str]:
    active_props, conflicts = _summarise_claims(entity.claims, entity.properties)
    head = f"- [{entity.id}] {entity.name} [{entity.entity_type}]"
    prop_summary = _format_properties(active_props)
    if prop_summary:
        head += f": {prop_summary}"
    if entity.contributing_sources:
        head += f" | sources: {', '.join(entity.contributing_sources)}"
    lines = [head]
    lines.extend(f"  ! {conflict}" for conflict in conflicts)
    return lines


def _relation_lines(relation: Relation, names_by_id: dict[UUID, str]) -> list[str]:
    active_props, conflicts = _summarise_claims(relation.claims, relation.properties)
    source_name = names_by_id.get(relation.source_entity_id, str(relation.source_entity_id))
    target_name = names_by_id.get(relation.target_entity_id, str(relation.target_entity_id))
    head = f"- {source_name} -[{relation.relation_type}]-> {target_name}"
    prop_summary = _format_properties(active_props)
    if prop_summary:
        head += f": {prop_summary}"
    if relation.contributing_sources:
        head += f" | sources: {', '.join(relation.contributing_sources)}"
    lines = [head]
    lines.extend(f"  ! {conflict}" for conflict in conflicts)
    return lines


def serialise_subgraph(result: RecallResult) -> str:
    """Compact, readable text representation of a RecallResult for the prompt.

    Not JSON and not a full Pydantic dump -- one line per entity (with its
    bracketed id so the model can cite it into grounded_entity_ids) and one
    line per relation (referencing entities by name), with active property
    values, contributing sources, and any conflict notes.
    """
    names_by_id = {entity.id: entity.name for entity in result.entities}

    lines = [f"QUERY: {result.query}", "", "ENTITIES:"]
    if result.entities:
        for entity in result.entities:
            lines.extend(_entity_lines(entity))
    else:
        lines.append("(none)")

    lines += ["", "RELATIONS:"]
    if result.relations:
        for relation in result.relations:
            lines.extend(_relation_lines(relation, names_by_id))
    else:
        lines.append("(none)")

    return "\n".join(lines)


class RecallSynthesiser:
    """Synthesise a prose answer from a RecallResult via Haiku 4.5.

    `client` is injectable (an Instructor-wrapped Anthropic async client) so
    unit tests can run fully offline; in production it's built lazily from
    settings, mirroring extraction/extractor.py and core/classifier.py.
    """

    def __init__(self, client: instructor.AsyncInstructor | None = None) -> None:
        self._client = client

    def _get_client(self) -> instructor.AsyncInstructor:
        if self._client is None:
            settings = get_settings()
            self._client = instructor.from_anthropic(
                anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
            )
        return self._client

    async def synthesise(
        self,
        query: str,
        result: RecallResult,
        scope: Scope,
    ) -> SynthesisResult:
        # No retrieved entities -> nothing to ground an answer in. Short-circuit
        # without an LLM call: the contract is "never hallucinate when the graph
        # has no relevant data", and an empty subgraph is exactly that case.
        if not result.entities:
            return SynthesisResult(
                answer="The retrieved memory does not contain information to answer this query.",
                grounded_entity_ids=[],
                confidence="insufficient_data",
                caveat="No entities were retrieved from the graph for this query.",
            )

        settings = get_settings()
        client = self._get_client()
        synthesis: SynthesisResult = await client.chat.completions.create(
            model=settings.synthesis_model,
            max_tokens=1024,
            system=SYNTHESIS_SYSTEM_PROMPT,
            response_model=SynthesisResult,
            messages=[{"role": "user", "content": serialise_subgraph(result)}],
        )

        # Keep only ids the model cited that actually exist in the subgraph, so
        # grounding can't reference an entity that wasn't retrieved.
        valid_ids = {str(entity.id) for entity in result.entities}
        synthesis.grounded_entity_ids = [
            entity_id for entity_id in synthesis.grounded_entity_ids if entity_id in valid_ids
        ]
        logger.debug(
            "recall.synthesised",
            tenant_id=scope.tenant_id,
            query=query,
            confidence=synthesis.confidence,
            grounded_count=len(synthesis.grounded_entity_ids),
        )
        return synthesis
