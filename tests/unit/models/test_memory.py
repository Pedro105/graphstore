from uuid import UUID

import pytest
from pydantic import ValidationError

from contextstore.models.entity import Entity
from contextstore.models.memory import Memory
from contextstore.models.provenance import Provenance
from contextstore.models.relation import Relation
from contextstore.models.scope import Scope


def make_memory(**overrides) -> Memory:
    defaults = dict(
        content="Pedro works at Acme.",
        scope=Scope.from_dict({"tenant_id": "acme", "user_id": "u_123"}),
        provenance=Provenance(source="agent_1"),
    )
    defaults.update(overrides)
    return Memory(**defaults)


def test_minimal_memory_has_generated_id_and_empty_lists():
    memory = make_memory()
    assert isinstance(memory.id, UUID)
    assert memory.entities == []
    assert memory.relations == []


def test_empty_content_is_invalid():
    with pytest.raises(ValidationError):
        make_memory(content="")


def test_memory_with_nested_entities_and_relations():
    scope = Scope.from_dict({"tenant_id": "acme", "user_id": "u_123"})
    provenance = Provenance(source="agent_1")
    pedro = Entity(name="Pedro", entity_type="person", scope=scope, provenance=provenance)
    acme = Entity(name="Acme", entity_type="org", scope=scope, provenance=provenance)
    works_at = Relation(
        source_entity_id=pedro.id,
        target_entity_id=acme.id,
        relation_type="works_at",
        scope=scope,
        provenance=provenance,
    )

    memory = make_memory(entities=[pedro, acme], relations=[works_at])

    assert memory.entities == [pedro, acme]
    assert memory.relations == [works_at]


def test_json_roundtrip_with_nested_entities_and_relations():
    scope = Scope.from_dict({"tenant_id": "acme", "user_id": "u_123"})
    provenance = Provenance(source="agent_1")
    pedro = Entity(name="Pedro", entity_type="person", scope=scope, provenance=provenance)
    acme = Entity(name="Acme", entity_type="org", scope=scope, provenance=provenance)
    works_at = Relation(
        source_entity_id=pedro.id,
        target_entity_id=acme.id,
        relation_type="works_at",
        scope=scope,
        provenance=provenance,
    )
    memory = make_memory(entities=[pedro, acme], relations=[works_at])

    restored = Memory.model_validate_json(memory.model_dump_json())
    assert restored == memory
