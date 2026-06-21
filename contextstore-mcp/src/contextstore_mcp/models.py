"""Minimal response models for the fields this server actually reads.

The ContextStore API returns much richer objects (full Scope, Claim, provenance
history, retrieval stats, ...), but this thin client only needs a handful of
fields to format its tool output. These models capture exactly those; pydantic
ignores everything else in the response, so they stay valid as the API grows --
and the package depends on nothing from the backend's model layer.
"""

from uuid import UUID

from pydantic import BaseModel


class Entity(BaseModel):
    id: UUID | None = None
    name: str
    entity_type: str


class Provenance(BaseModel):
    source: str
    confidence: float = 1.0


class Relation(BaseModel):
    source_entity_id: UUID
    target_entity_id: UUID
    relation_type: str
    provenance: Provenance


class Synthesis(BaseModel):
    answer: str
    caveat: str | None = None


class RememberResult(BaseModel):
    """The /v1/memories response, narrowed to what the tool reports back."""

    entities: list[Entity] = []


class RecallResult(BaseModel):
    """The /v1/recall response, narrowed to what the tool formats."""

    entities: list[Entity] = []
    relations: list[Relation] = []
    synthesis: Synthesis | None = None
