"""Extraction-time intermediate representations.

These are deliberately not the full Entity/Relation models: scope and
provenance are attached later by the orchestrating service
(core/service.py), once entities have been resolved against the graph.
"""

from typing import Any

from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    name: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    properties: dict[str, Any] = Field(default_factory=dict)


class ExtractedRelation(BaseModel):
    source_name: str = Field(min_length=1)
    target_name: str = Field(min_length=1)
    relation_type: str = Field(min_length=1)
    properties: dict[str, Any] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    """Wrapper used as the Instructor response_model (a single structured call)."""

    entities: list[ExtractedEntity] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)
