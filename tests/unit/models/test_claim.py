from contextstore.models.claim import apply_claim, derive_active_view
from contextstore.models.provenance import Provenance


def test_no_properties_records_a_single_touch_claim():
    claims = apply_claim([], Provenance(source="agent_1"), {})

    assert len(claims) == 1
    assert claims[0].property_name is None
    assert claims[0].value is None


def test_new_property_claim_does_not_supersede_anything():
    claims = apply_claim([], Provenance(source="agent_1"), {"price": "4.20"})

    assert len(claims) == 1
    assert claims[0].provenance.supersedes is None


def test_same_value_from_different_source_does_not_supersede():
    claims = apply_claim([], Provenance(source="agent_1"), {"price": "4.20"})
    claims = apply_claim(claims, Provenance(source="agent_2"), {"price": "4.20"})

    assert len(claims) == 2
    assert claims[1].provenance.supersedes is None
    properties, provenance, sources = derive_active_view(claims)
    assert properties == {"price": "4.20"}
    assert sources == ["agent_1", "agent_2"]


def test_different_value_supersedes_prior_claim_for_that_property():
    claims = apply_claim([], Provenance(source="agent_1"), {"price": "4.20"})
    old_claim = claims[0]
    claims = apply_claim(claims, Provenance(source="agent_1"), {"price": "4.50"})

    assert len(claims) == 2
    new_claim = claims[1]
    assert new_claim.provenance.supersedes == [str(old_claim.id)]

    properties, provenance, sources = derive_active_view(claims)
    assert properties == {"price": "4.50"}
    assert provenance.source == "agent_1"
    assert sources == ["agent_1"]


def test_different_source_with_different_value_also_supersedes():
    claims = apply_claim([], Provenance(source="agent_1"), {"price": "4.20"})
    old_claim = claims[0]
    claims = apply_claim(claims, Provenance(source="agent_2"), {"price": "4.50"})

    new_claim = claims[1]
    assert new_claim.provenance.supersedes == [str(old_claim.id)]
    properties, provenance, sources = derive_active_view(claims)
    assert properties == {"price": "4.50"}
    assert provenance.source == "agent_2"
    assert sources == ["agent_1", "agent_2"]


def test_unrelated_properties_do_not_supersede_each_other():
    claims = apply_claim([], Provenance(source="agent_1"), {"price": "4.20"})
    claims = apply_claim(claims, Provenance(source="agent_2"), {"quantity": "400"})

    properties, _, sources = derive_active_view(claims)
    assert properties == {"price": "4.20", "quantity": "400"}
    assert sources == ["agent_1", "agent_2"]
    assert all(claim.provenance.supersedes is None for claim in claims)


def test_derive_active_view_keeps_full_history_even_after_supersession():
    claims = apply_claim([], Provenance(source="agent_1"), {"price": "4.20"})
    claims = apply_claim(claims, Provenance(source="agent_1"), {"price": "4.50"})

    assert len(claims) == 2
    assert claims[0].value == "4.20"
    assert claims[1].value == "4.50"
