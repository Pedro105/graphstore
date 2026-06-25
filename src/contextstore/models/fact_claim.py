"""FactClaim: a reified fact in the graph -- a `:Claim` node connecting a
subject entity to an object entity, carrying the coherence state (status,
validity, provenance, supersession, disputes) that a bare typed edge could not.

This is the unit of multi-agent coherence: several agents can assert, corroborate
or contest the same fact, and a fact can be superseded or marked disputed without
ever being deleted. Distinct from the property-level `models/claim.py::Claim`,
which is *kept and nested* inside a FactClaim (`FactClaim.claims`) to track
revisions of a fact's own properties (e.g. a revised price on the same fact).

`ClaimAssertion` is the transient input the write path hands the adjudicator
(resolution/conflict_resolver.py): one extracted, entity-resolved relation plus
its assertion semantics. It is never persisted -- the adjudicator turns it into
FactClaim(s).
"""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from contextstore.extraction.schemas import AssertionType
from contextstore.models.claim import Claim
from contextstore.models.provenance import Provenance
from contextstore.models.scope import Scope

ClaimStatus = Literal["active", "superseded", "disputed", "retracted"]
# Statuses that represent current truth and so appear in the default graph /
# recall views (the collapse projection). superseded/retracted are history,
# reachable only via inspection.
LIVE_STATUSES: tuple[ClaimStatus, ...] = ("active", "disputed")


def _now() -> datetime:
    return datetime.now(UTC)


class FactClaim(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    # Normalized predicate (used for matching conflicting claims); raw_predicate
    # is the original free-string relation type from extraction (for display).
    predicate: str = Field(min_length=1)
    raw_predicate: str = Field(min_length=1)
    subject_id: UUID
    object_id: UUID
    status: ClaimStatus = "active"
    # Every source/agent that has asserted this exact fact (subject+predicate+object).
    asserted_by: list[str] = Field(default_factory=list)
    support_count: int = 1
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    valid_from: datetime = Field(default_factory=_now)
    # Set when the claim leaves active (superseded/retracted); None while live.
    valid_to: datetime | None = None
    # Claim ids this claim replaced (set on the new claim when it supersedes).
    supersedes: list[UUID] = Field(default_factory=list)
    # Live, unresolved conflicts with claims from other asserters (mutual link).
    disputed_with: list[UUID] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    last_seen: datetime = Field(default_factory=_now)
    # Active property view + the property-level claim history backing it
    # (models/claim.py) -- e.g. a revised price on this same fact.
    properties: dict[str, Any] = Field(default_factory=dict)
    claims: list[Claim] = Field(default_factory=list)
    scope: Scope


class ClaimAssertion(BaseModel):
    """One entity-resolved, extracted relation handed to the adjudicator.

    Transient: built by core/service.py from an ExtractedRelation plus the
    resolved subject/object entity ids and this write's provenance. Never stored.
    """

    subject_id: UUID
    object_id: UUID
    subject_name: str = Field(min_length=1)
    object_name: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    raw_predicate: str = Field(min_length=1)
    assertion_type: AssertionType = "asserted"
    as_of: str | None = None
    replaces_hint: bool = False
    properties: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance
    scope: Scope

    @property
    def asserter(self) -> str:
        return self.provenance.source

    @property
    def has_recency_signal(self) -> bool:
        """Whether the text marked this as a current/new state replacing a prior
        one -- the deterministic supersession trigger (no LLM needed)."""
        return self.replaces_hint or self.as_of is not None
