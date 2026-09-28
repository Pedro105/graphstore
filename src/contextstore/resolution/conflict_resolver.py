"""Claim adjudication: decide what a newly asserted fact does to the existing
active claims about the same subject+predicate.

Heuristic-first, Haiku-fallback (mirrors core/classifier.py): the common,
unambiguous cases (corroboration, termination, same-agent update with a recency
signal, cross-agent conflict) are decided deterministically with no LLM call;
only a same-subject/same-predicate/different-object assertion with *no* recency
signal needs the LLM, and only to answer "are these objects mutually exclusive,
and if so does this supersede or dispute?".

Cardinality is adjudicated, never declared: there is no config of "functional"
relations. `works_at A` vs `works_at B` resolves to supersede/dispute;
`collaborated_with X` vs `collaborated_with Y` resolves to independent -- the LLM
makes that call per claim-pair.

`adjudicate` returns the list of FactClaims the write path must upsert: the new
claim plus any existing claims whose status changed. It never deletes anything.
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

import anthropic
import instructor
import structlog
from pydantic import BaseModel, Field

from contextstore.core.config import get_settings
from contextstore.models.claim import apply_claim, derive_active_view
from contextstore.models.fact_claim import ClaimAssertion, ClaimStatus, FactClaim

logger = structlog.get_logger()

# Below this LLM confidence on a same-asserter conflict, default to `disputed`
# rather than committing to a supersede -- the safe multi-agent default.
JUDGE_CONFIDENCE_THRESHOLD = 0.6


def _now() -> datetime:
    return datetime.now(UTC)


def _new_claim(
    assertion: ClaimAssertion,
    status: ClaimStatus,
    *,
    valid_to: datetime | None = None,
    supersedes: list[UUID] | None = None,
) -> FactClaim:
    claims = apply_claim([], assertion.provenance, assertion.properties)
    properties, _provenance, _sources = derive_active_view(claims)
    return FactClaim(
        predicate=assertion.predicate,
        raw_predicate=assertion.raw_predicate,
        subject_id=assertion.subject_id,
        object_id=assertion.object_id,
        status=status,
        asserted_by=[assertion.asserter],
        support_count=1,
        confidence=assertion.provenance.confidence,
        valid_to=valid_to,
        supersedes=list(supersedes or []),
        properties=properties,
        claims=claims,
        scope=assertion.scope,
    )


def _corroborate(claim: FactClaim, assertion: ClaimAssertion) -> FactClaim:
    """Row 3: the same fact asserted again. Bump support, add the asserter, fold
    in any property revision -- one active claim, not a duplicate."""
    merged_claims = apply_claim(claim.claims, assertion.provenance, assertion.properties)
    properties, _provenance, _sources = derive_active_view(merged_claims)
    asserted_by = (
        claim.asserted_by
        if assertion.asserter in claim.asserted_by
        else [*claim.asserted_by, assertion.asserter]
    )
    return claim.model_copy(
        update={
            "support_count": claim.support_count + 1,
            "asserted_by": asserted_by,
            "properties": properties,
            "claims": merged_claims,
            "last_seen": _now(),
        }
    )


def _retract(claim: FactClaim) -> FactClaim:
    return claim.model_copy(update={"status": "retracted", "valid_to": _now()})


def _supersede(assertion: ClaimAssertion, candidates: list[FactClaim]) -> list[FactClaim]:
    now = _now()
    superseded = [c.model_copy(update={"status": "superseded", "valid_to": now}) for c in candidates]
    new = _new_claim(assertion, "active", supersedes=[c.id for c in candidates])
    return [*superseded, new]


def _dispute(assertion: ClaimAssertion, candidates: list[FactClaim]) -> list[FactClaim]:
    new = _new_claim(assertion, "disputed")
    new = new.model_copy(update={"disputed_with": [c.id for c in candidates]})
    disputed_candidates = [
        c.model_copy(
            update={
                "status": "disputed",
                "disputed_with": (
                    c.disputed_with if new.id in c.disputed_with else [*c.disputed_with, new.id]
                ),
            }
        )
        for c in candidates
    ]
    return [new, *disputed_candidates]


def _has_other_asserter(candidates: list[FactClaim], asserter: str) -> bool:
    """True if any conflicting candidate was asserted by someone other than the
    new asserter -- the trigger that forces a dispute over a silent supersede."""
    return any(source != asserter for c in candidates for source in c.asserted_by)


class AdjudicationVerdict(BaseModel):
    """Instructor response_model for the LLM fallback (row 6)."""

    verdict: Literal["independent", "supersede", "dispute"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)


_JUDGE_SYSTEM_PROMPT = """\
You adjudicate a potential conflict between two facts in a knowledge graph. A \
subject already has one or more ACTIVE relationships of a given type, and a new \
write asserts the same relationship type from the same subject toward a \
DIFFERENT object. Decide which of three things is true:

- independent: the subject can genuinely hold BOTH at once -- the relationship \
type is naturally multi-valued (e.g. collaborated_with, knows, mentions, \
authored). Both facts stay true. Choose this whenever the objects are not \
mutually exclusive.
- supersede: the new fact REPLACES the old one -- the relationship type is \
single-valued for a subject at a time (e.g. current employer, current status, \
capital_of) and the new assertion is an update to the same slot.
- dispute: the relationship is single-valued AND the two facts genuinely \
contradict each other with no signal that one replaces the other (so they \
should be flagged as conflicting, not silently merged).

Judge primarily from the relationship type's natural cardinality. Put a \
one-sentence justification in `reason` and a calibrated confidence in [0,1].\
"""


class ClaimJudge:
    """LLM fallback: Haiku 4.5 via Instructor, same pattern as LLMClassifier."""

    async def judge(
        self, assertion: ClaimAssertion, candidates: list[FactClaim]
    ) -> AdjudicationVerdict:
        settings = get_settings()
        client = instructor.from_anthropic(
            anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
        )
        existing = ", ".join(sorted({c.raw_predicate for c in candidates})) or assertion.raw_predicate
        user = (
            f"Subject: {assertion.subject_name}\n"
            f"Relationship type: {assertion.raw_predicate}\n"
            f"Existing active object(s) for this subject+type: "
            f"{len(candidates)} (type {existing})\n"
            f"New asserted object: {assertion.object_name}\n"
            "Does the new fact stand independently, supersede the existing one(s), "
            "or dispute them?"
        )
        result: AdjudicationVerdict = await client.chat.completions.create(
            model=settings.classifier_model,
            max_tokens=512,
            system=_JUDGE_SYSTEM_PROMPT,
            response_model=AdjudicationVerdict,
            messages=[{"role": "user", "content": user}],
        )
        return result


async def adjudicate(
    assertion: ClaimAssertion,
    candidates: list[FactClaim],
    judge: ClaimJudge | None = None,
) -> list[FactClaim]:
    """Decide the new assertion against the active `candidates` (same subject +
    same normalized predicate). Returns the FactClaims to upsert."""
    same_object = [c for c in candidates if c.object_id == assertion.object_id]
    other_object = [c for c in candidates if c.object_id != assertion.object_id]

    # Rows 1-2: terminations / negations -> retract, never assert.
    if assertion.assertion_type in ("terminated", "negated"):
        if same_object:
            return [_retract(c) for c in same_object]
        # No matching active claim: record the negation as a retracted claim so
        # the explicit denial is preserved (claims are never silently dropped).
        return [_new_claim(assertion, "retracted", valid_to=_now())]

    # Row 3: corroboration (exact same fact).
    if same_object:
        return [_corroborate(same_object[0], assertion)]

    # Row 7: nothing to conflict with.
    if not other_object:
        return [_new_claim(assertion, "active")]

    # Rows 4-6: different object for the same subject+predicate.
    cross_asserter = _has_other_asserter(other_object, assertion.asserter)

    if assertion.has_recency_signal:
        # The text frames this as the current/new state: a deliberate update.
        # Same asserter -> supersede; different asserter -> dispute (locked rule:
        # never silently overwrite another agent's claim).
        decision: Literal["supersede", "dispute"] = "dispute" if cross_asserter else "supersede"
    else:
        verdict = await (judge or ClaimJudge()).judge(assertion, other_object)
        logger.debug(
            "adjudicate.llm",
            subject=str(assertion.subject_id),
            predicate=assertion.predicate,
            verdict=verdict.verdict,
            confidence=verdict.confidence,
            reason=verdict.reason,
        )
        if verdict.verdict == "independent":
            return [_new_claim(assertion, "active")]
        if cross_asserter:
            decision = "dispute"
        elif verdict.confidence < JUDGE_CONFIDENCE_THRESHOLD:
            decision = "dispute"  # ambiguous same-asserter conflict -> safe default
        else:
            decision = verdict.verdict  # supersede or dispute, as judged

    if decision == "supersede":
        return _supersede(assertion, other_object)
    return _dispute(assertion, other_object)
