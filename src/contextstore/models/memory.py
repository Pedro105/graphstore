"""Memory: the atomic unit of written knowledge, decomposed into entities and relations."""

from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from contextstore.models.entity import Entity
from contextstore.models.provenance import Provenance
from contextstore.models.relation import Relation
from contextstore.models.scope import Scope


class Memory(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    content: str = Field(min_length=1)
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    scope: Scope
    provenance: Provenance
