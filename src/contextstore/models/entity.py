"""Entity: a node in the knowledge graph (a person, thing, or concept)."""

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from contextstore.models.claim import Claim
from contextstore.models.provenance import Provenance
from contextstore.models.scope import Scope


class Entity(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    # Every entity_type ever observed for this node, canonical one included.
    # Entity resolution no longer hard-partitions on type (the same real-world
    # thing tagged Organization by one agent and Product by another used to
    # fork into two nodes); instead it merges and accumulates the disagreement
    # here. `entity_type` stays the canonical/first-writer value (so the UI's
    # colour/type label is stable); `observed_types` records the full set.
    observed_types: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    scope: Scope
    provenance: Provenance
    embedding: list[float] | None = None
    merge_candidates: list[UUID] = Field(default_factory=list)
    # Full claim history backing `properties`/`provenance` above (see
    # models/claim.py) -- multiple, possibly conflicting, sources are kept
    # rather than the first or last writer silently winning.
    claims: list[Claim] = Field(default_factory=list)
    contributing_sources: list[str] = Field(default_factory=list)
