from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from contextstore.models.provenance import Provenance
from contextstore.models.relation import Relation
from contextstore.models.scope import Scope


def make_relation(**overrides) -> Relation:
    defaults = dict(
        source_entity_id=uuid4(),
        target_entity_id=uuid4(),
        relation_type="works_at",
        scope=Scope.from_dict({"tenant_id": "acme", "user_id": "u_123"}),
        provenance=Provenance(source="agent_1"),
    )
    defaults.update(overrides)
    return Relation(**defaults)


def test_minimal_relation_has_generated_id():
    relation = make_relation()
    assert isinstance(relation.id, UUID)
    assert relation.properties == {}


def test_empty_relation_type_is_invalid():
    with pytest.raises(ValidationError):
        make_relation(relation_type="")


def test_entity_ids_accept_uuid_strings():
    source_id = uuid4()
    target_id = uuid4()
    relation = make_relation(source_entity_id=str(source_id), target_entity_id=str(target_id))
    assert relation.source_entity_id == source_id
    assert relation.target_entity_id == target_id


def test_json_roundtrip():
    relation = make_relation(properties={"since": "2024"})
    restored = Relation.model_validate_json(relation.model_dump_json())
    assert restored == relation
