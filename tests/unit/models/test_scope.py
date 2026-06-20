import pytest
from pydantic import ValidationError

from contextstore.models.scope import Scope


def test_from_dict_and_to_query_dict_roundtrip():
    scope = Scope.from_dict({"tenant_id": "acme", "project": "alpha", "agent_id": "researcher_1"})
    assert scope.to_query_dict() == {
        "tenant_id": "acme",
        "project": "alpha",
        "agent_id": "researcher_1",
    }


def test_tenant_id_property():
    scope = Scope.from_dict({"tenant_id": "acme", "project": "alpha"})
    assert scope.tenant_id == "acme"


def test_broader_scope_includes_narrower_scope():
    broader = Scope.from_dict({"tenant_id": "acme", "project": "alpha"})
    narrower = Scope.from_dict(
        {"tenant_id": "acme", "project": "alpha", "agent_id": "researcher_1"}
    )
    assert broader.includes(narrower) is True


def test_narrower_scope_does_not_include_broader_scope():
    broader = Scope.from_dict({"tenant_id": "acme", "project": "alpha"})
    narrower = Scope.from_dict(
        {"tenant_id": "acme", "project": "alpha", "agent_id": "researcher_1"}
    )
    assert narrower.includes(broader) is False


def test_scope_includes_itself():
    scope = Scope.from_dict({"tenant_id": "acme", "user_id": "u_123"})
    assert scope.includes(scope) is True


def test_disjoint_scopes_do_not_include_each_other():
    a = Scope.from_dict({"tenant_id": "acme", "user_id": "u_123"})
    b = Scope.from_dict({"tenant_id": "acme", "workflow_id": "nightly_triage"})
    assert a.includes(b) is False
    assert b.includes(a) is False


def test_mismatched_value_for_same_key_does_not_include():
    a = Scope.from_dict({"tenant_id": "acme", "project": "alpha"})
    b = Scope.from_dict({"tenant_id": "acme", "project": "beta"})
    assert a.includes(b) is False


def test_different_tenants_never_include_each_other_even_with_identical_other_keys():
    a = Scope.from_dict({"tenant_id": "acme", "project": "alpha"})
    b = Scope.from_dict({"tenant_id": "globex", "project": "alpha"})
    assert a.includes(b) is False
    assert b.includes(a) is False


def test_empty_scope_is_invalid():
    with pytest.raises(ValidationError):
        Scope.from_dict({})


def test_missing_tenant_id_is_invalid():
    with pytest.raises(ValidationError):
        Scope.from_dict({"project": "alpha"})


@pytest.mark.parametrize("tenant_id", [123, "", "acme corp", "acme/corp", "acme!"])
def test_invalid_tenant_id_values_are_rejected(tenant_id):
    with pytest.raises(ValidationError):
        Scope.from_dict({"tenant_id": tenant_id})


def test_empty_key_is_invalid():
    with pytest.raises(ValidationError):
        Scope.from_dict({"tenant_id": "acme", "": "value"})


def test_serialization_is_flat_dict():
    scope = Scope.from_dict({"tenant_id": "acme", "project": "alpha"})
    assert scope.model_dump() == {"tenant_id": "acme", "project": "alpha"}


def test_json_roundtrip():
    scope = Scope.from_dict({"tenant_id": "acme", "project": "alpha", "run_id": 7})
    restored = Scope.model_validate_json(scope.model_dump_json())
    assert restored == scope
