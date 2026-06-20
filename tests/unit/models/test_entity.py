from uuid import UUID

import pytest
from pydantic import ValidationError

from contextstore.models.entity import Entity
from contextstore.models.provenance import Provenance
from contextstore.models.scope import Scope


def make_entity(**overrides) -> Entity:
    defaults = dict(
        name="Pedro Costa",
        entity_type="person",
        scope=Scope.from_dict({"tenant_id": "acme", "user_id": "u_123"}),
        provenance=Provenance(source="agent_1"),
    )
    defaults.update(overrides)
    return Entity(**defaults)


def test_minimal_entity_has_generated_id():
    entity = make_entity()
    assert isinstance(entity.id, UUID)
    assert entity.properties == {}
    assert entity.embedding is None


def test_each_entity_gets_a_unique_id():
    assert make_entity().id != make_entity().id


@pytest.mark.parametrize("field", ["name", "entity_type"])
def test_empty_required_string_fields_are_invalid(field):
    with pytest.raises(ValidationError):
        make_entity(**{field: ""})


def test_entity_with_embedding_and_properties():
    entity = make_entity(properties={"role": "engineer"}, embedding=[0.1, 0.2, 0.3])
    assert entity.properties == {"role": "engineer"}
    assert entity.embedding == [0.1, 0.2, 0.3]


def test_json_roundtrip():
    entity = make_entity(properties={"role": "engineer"}, embedding=[0.1, 0.2])
    restored = Entity.model_validate_json(entity.model_dump_json())
    assert restored == entity
