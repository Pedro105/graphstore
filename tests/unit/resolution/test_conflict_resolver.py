"""Unit tests for the claim adjudicator decision table (resolution/
conflict_resolver.py). The LLM fallback (row 6) is mocked -- no API key, no
FalkorDB. These pin the deterministic branches; the live, end-to-end behaviour
is the five named integration evals (test_coherence_evals.py).
"""

from uuid import uuid4

from contextstore.models.fact_claim import ClaimAssertion, FactClaim
from contextstore.models.provenance import Provenance
from contextstore.models.scope import Scope
from contextstore.resolution.conflict_resolver import AdjudicationVerdict, adjudicate

SCOPE = Scope.from_dict({"tenant_id": "acme"})
SUBJECT = uuid4()
OBJECT_A = uuid4()
OBJECT_B = uuid4()


class FakeJudge:
    def __init__(self, verdict: str, confidence: float = 0.9) -> None:
        self._verdict = AdjudicationVerdict(verdict=verdict, confidence=confidence, reason="test")
        self.calls = 0

    async def judge(self, assertion, candidates):  # noqa: ANN001
        self.calls += 1
        return self._verdict


def make_assertion(object_id=OBJECT_A, asserter="agent_a", **overrides) -> ClaimAssertion:
    defaults = dict(
        subject_id=SUBJECT,
        object_id=object_id,
        subject_name="Pedro",
        object_name="Company",
        predicate="works_at",
        raw_predicate="works_at",
        provenance=Provenance(source=asserter),
        scope=SCOPE,
    )
    defaults.update(overrides)
    return ClaimAssertion(**defaults)


def make_candidate(object_id=OBJECT_A, asserter="agent_a", **overrides) -> FactClaim:
    defaults = dict(
        predicate="works_at",
        raw_predicate="works_at",
        subject_id=SUBJECT,
        object_id=object_id,
        status="active",
        asserted_by=[asserter],
        scope=SCOPE,
    )
    defaults.update(overrides)
    return FactClaim(**defaults)


async def test_row7_no_candidates_creates_active_claim():
    out = await adjudicate(make_assertion(), [])
    assert len(out) == 1
    assert out[0].status == "active"
    assert out[0].asserted_by == ["agent_a"]


async def test_row3_same_triple_corroborates():
    candidate = make_candidate(object_id=OBJECT_A, asserter="agent_a")
    out = await adjudicate(make_assertion(object_id=OBJECT_A, asserter="agent_b"), [candidate])
    assert len(out) == 1
    assert out[0].id == candidate.id  # same claim, not a new one
    assert out[0].support_count == 2
    assert set(out[0].asserted_by) == {"agent_a", "agent_b"}


async def test_row1_termination_retracts_matching_claim():
    candidate = make_candidate(object_id=OBJECT_A)
    out = await adjudicate(
        make_assertion(object_id=OBJECT_A, assertion_type="terminated"), [candidate]
    )
    assert len(out) == 1
    assert out[0].id == candidate.id
    assert out[0].status == "retracted"
    assert out[0].valid_to is not None


async def test_row2_negation_without_match_records_retracted_claim():
    out = await adjudicate(make_assertion(assertion_type="negated"), [])
    assert len(out) == 1
    assert out[0].status == "retracted"


async def test_row4_same_asserter_with_recency_signal_supersedes():
    candidate = make_candidate(object_id=OBJECT_A, asserter="agent_a")
    out = await adjudicate(
        make_assertion(object_id=OBJECT_B, asserter="agent_a", replaces_hint=True), [candidate]
    )
    by_status = {c.status: c for c in out}
    assert by_status["superseded"].id == candidate.id
    assert by_status["superseded"].valid_to is not None
    new = by_status["active"]
    assert new.object_id == OBJECT_B
    assert candidate.id in new.supersedes


async def test_row5_different_asserter_with_signal_disputes_not_supersedes():
    candidate = make_candidate(object_id=OBJECT_A, asserter="agent_a")
    out = await adjudicate(
        make_assertion(object_id=OBJECT_B, asserter="agent_b", as_of="now"), [candidate]
    )
    assert all(c.status == "disputed" for c in out)
    new = next(c for c in out if c.object_id == OBJECT_B)
    old = next(c for c in out if c.id == candidate.id)
    assert candidate.id in new.disputed_with
    assert new.id in old.disputed_with


async def test_row6_independent_keeps_both_active():
    judge = FakeJudge("independent")
    candidate = make_candidate(object_id=OBJECT_A, asserter="agent_a")
    out = await adjudicate(
        make_assertion(object_id=OBJECT_B, asserter="agent_a"), [candidate], judge=judge
    )
    assert judge.calls == 1
    assert len(out) == 1
    assert out[0].status == "active"
    assert out[0].object_id == OBJECT_B  # candidate untouched, both live


async def test_row6_same_asserter_supersede_verdict_supersedes():
    judge = FakeJudge("supersede", confidence=0.9)
    candidate = make_candidate(object_id=OBJECT_A, asserter="agent_a")
    out = await adjudicate(
        make_assertion(object_id=OBJECT_B, asserter="agent_a"), [candidate], judge=judge
    )
    by_status = {c.status: c for c in out}
    assert by_status["superseded"].id == candidate.id
    assert by_status["active"].object_id == OBJECT_B


async def test_row6_cross_asserter_always_disputes_even_if_judge_says_supersede():
    judge = FakeJudge("supersede", confidence=0.99)
    candidate = make_candidate(object_id=OBJECT_A, asserter="agent_a")
    out = await adjudicate(
        make_assertion(object_id=OBJECT_B, asserter="agent_b"), [candidate], judge=judge
    )
    assert all(c.status == "disputed" for c in out)


async def test_row6_low_confidence_defaults_to_dispute():
    judge = FakeJudge("supersede", confidence=0.2)
    candidate = make_candidate(object_id=OBJECT_A, asserter="agent_a")
    out = await adjudicate(
        make_assertion(object_id=OBJECT_B, asserter="agent_a"), [candidate], judge=judge
    )
    assert all(c.status == "disputed" for c in out)
