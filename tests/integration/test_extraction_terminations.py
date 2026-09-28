"""Stage 1 acceptance probes: extraction must EMIT terminations and negations
rather than dropping them (the root cause of facts never being superseded).

These call real Claude (Haiku) via Instructor and skip gracefully when the API
isn't configured/reachable -- the same "attempt and skip on failure" pattern as
the other integration tests. They assert on `assertion_type`, the field added
in Stage 1; they do NOT touch FalkorDB (extraction is a pure LLM call).

Named scenarios -- these are the seed of the coherence benchmark, so keep them
clean and reusable.
"""

import pytest

from contextstore.extraction.extractor import extract
from contextstore.extraction.schemas import ExtractedRelation


async def _extract_or_skip(content: str) -> list[ExtractedRelation]:
    try:
        _entities, relations, _tokens = await extract(content)
    except Exception as exc:  # noqa: BLE001 -- mirror the repo's skip-on-failure E2E pattern
        pytest.skip(f"Real extraction LLM call failed -- check ANTHROPIC_API_KEY: {exc}")
    return relations


def _employment_relations(relations: list[ExtractedRelation], company_token: str) -> list[
    ExtractedRelation
]:
    """Relations whose target name contains `company_token` (case-insensitive).
    Loose on relation_type/name surface form, strict on assertion_type below."""
    token = company_token.casefold()
    return [r for r in relations if token in r.target_name.casefold()]


async def test_left_and_joined_yields_terminated_plus_asserted():
    """`two_employers` (extraction layer): "Pedro left ASML and joined ABN AMRO"
    must produce a TERMINATED works_at->ASML AND an ASSERTED works_at->ABN AMRO.
    Today (pre-Stage-1) the termination was silently dropped."""
    relations = await _extract_or_skip("Pedro left ASML and joined ABN AMRO.")

    asml = _employment_relations(relations, "ASML")
    abn = _employment_relations(relations, "ABN")

    assert asml, f"expected a relation to ASML, got {relations}"
    assert abn, f"expected a relation to ABN AMRO, got {relations}"
    assert any(r.assertion_type == "terminated" for r in asml), (
        f"expected ASML relation terminated, got {[r.assertion_type for r in asml]}"
    )
    assert any(r.assertion_type == "asserted" for r in abn), (
        f"expected ABN AMRO relation asserted, got {[r.assertion_type for r in abn]}"
    )


async def test_explicit_negation_is_marked_negated():
    """"Pedro does not work at ASML" -> a works_at->ASML relation flagged
    negated (not dropped, not asserted)."""
    relations = await _extract_or_skip("Pedro does not work at ASML.")

    asml = _employment_relations(relations, "ASML")
    assert asml, f"expected a relation to ASML, got {relations}"
    assert any(r.assertion_type == "negated" for r in asml), (
        f"expected ASML relation negated, got {[r.assertion_type for r in asml]}"
    )


async def test_plain_statement_stays_asserted():
    """Regression: an ordinary statement is unchanged -- assertion_type asserted."""
    relations = await _extract_or_skip("Pedro works at ASML.")

    asml = _employment_relations(relations, "ASML")
    assert asml, f"expected a relation to ASML, got {relations}"
    assert all(r.assertion_type == "asserted" for r in asml), (
        f"expected all ASML relations asserted, got {[r.assertion_type for r in asml]}"
    )
