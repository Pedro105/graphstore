"""Relation: a typed edge between two entities in the knowledge graph."""

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from contextstore.models.claim import Claim
from contextstore.models.provenance import Provenance
from contextstore.models.scope import Scope


class Relation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_entity_id: UUID
    target_entity_id: UUID
    relation_type: str = Field(min_length=1)
    properties: dict[str, Any] = Field(default_factory=dict)
    scope: Scope
    provenance: Provenance
    # See Entity.claims/contributing_sources -- same multi-source tracking,
    # since relations (e.g. a supplier's quoted price) freeze on repeat
    # writes the same way entity properties do.
    claims: list[Claim] = Field(default_factory=list)
    contributing_sources: list[str] = Field(default_factory=list)
    # Coherence state, set when this Relation is a display edge collapsed from a
    # FactClaim (see graph/falkordb_store.py's projection). "active" for an
    # undisputed current fact; "disputed" when live claims from different
    # asserters conflict. `disputed_with` lists the conflicting claim ids.
    # Defaults keep plain (write-time) Relations unaffected.
    status: str = "active"
    disputed_with: list[UUID] = Field(default_factory=list)
