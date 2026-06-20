from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from contextstore.models.provenance import Provenance


def test_minimal_provenance_has_sane_defaults():
    p = Provenance(source="agent_1")
    assert p.confidence == 1.0
    assert p.evidence is None
    assert p.supersedes is None
    assert p.created_at.tzinfo is not None


def test_empty_source_is_invalid():
    with pytest.raises(ValidationError):
        Provenance(source="")


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_confidence_out_of_range_is_invalid(confidence):
    with pytest.raises(ValidationError):
        Provenance(source="agent_1", confidence=confidence)


@pytest.mark.parametrize("confidence", [0.0, 1.0, 0.5])
def test_confidence_boundaries_are_valid(confidence):
    p = Provenance(source="agent_1", confidence=confidence)
    assert p.confidence == confidence


def test_json_roundtrip():
    p = Provenance(
        source="agent_1",
        created_at=datetime(2026, 6, 17, tzinfo=UTC),
        confidence=0.8,
        evidence=["doc_1"],
        supersedes=["mem_123"],
    )
    restored = Provenance.model_validate_json(p.model_dump_json())
    assert restored == p
