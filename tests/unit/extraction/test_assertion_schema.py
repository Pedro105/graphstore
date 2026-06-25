"""Stage 1 unit coverage: the assertion-semantics fields on ExtractedRelation.

These tests need no API key -- they pin the schema contract (defaults,
backward compatibility) and prove the new fields pass through the write path
harmlessly (core/service.py still ignores them when building a Relation, since
Stage 2 is what will consume them).
"""

from uuid import uuid4

from contextstore.extraction.schemas import ExtractedRelation
from contextstore.models.relation import Relation
from contextstore.models.provenance import Provenance
from contextstore.models.scope import Scope

SCOPE = Scope.from_dict({"tenant_id": "acme"})


def test_assertion_type_defaults_to_asserted():
    rel = ExtractedRelation(source_name="Pedro", target_name="ASML", relation_type="works_at")
    assert rel.assertion_type == "asserted"
    assert rel.as_of is None
    assert rel.replaces_hint is False


def test_terminated_and_negated_are_representable():
    terminated = ExtractedRelation(
        source_name="Pedro",
        target_name="ASML",
        relation_type="works_at",
        assertion_type="terminated",
        as_of="2024",
    )
    negated = ExtractedRelation(
        source_name="Pedro",
        target_name="ASML",
        relation_type="works_at",
        assertion_type="negated",
    )
    assert terminated.assertion_type == "terminated"
    assert terminated.as_of == "2024"
    negated_assertion: str = negated.assertion_type
    assert negated_assertion == "negated"


def test_replaces_hint_carries_through():
    rel = ExtractedRelation(
        source_name="Pedro",
        target_name="ABN AMRO",
        relation_type="works_at",
        assertion_type="asserted",
        as_of="now",
        replaces_hint=True,
    )
    assert rel.replaces_hint is True
    assert rel.as_of == "now"


def test_new_fields_do_not_leak_into_the_relation_model():
    """The write path is unchanged in Stage 1: assertion semantics are not yet
    carried onto the persisted Relation. This guards against accidentally
    wiring them in before Stage 2's adjudication is designed."""
    extracted = ExtractedRelation(
        source_name="Pedro",
        target_name="ASML",
        relation_type="works_at",
        assertion_type="terminated",
    )
    # Build a Relation exactly as core/service.remember does today.
    relation = Relation(
        source_entity_id=uuid4(),
        target_entity_id=uuid4(),
        relation_type=extracted.relation_type,
        properties=extracted.properties,
        scope=SCOPE,
        provenance=Provenance(source="agent_1"),
    )
    assert not hasattr(relation, "assertion_type")
