"""Fact: one claim flattened out of the graph into a tabular row.

The operator facts table (api/admin_routes.py) reads `claims_json` off every
:Entity node and expands each claim into a Fact -- the same underlying data as
the per-entity claim history, but pivoted into a flat, searchable, cross-entity
(and cross-project) view. Not persisted: a Fact is a read-time projection."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class Fact(BaseModel):
    tenant_id: str
    entity_id: UUID
    entity_name: str
    entity_type: str
    # The asserted property; None for a bare "this source touched the entity"
    # claim (apply_claim records those so every writer is represented).
    property_name: str | None
    value: Any | None
    source: str
    asserted_at: datetime
    # True when a later claim's provenance supersedes this one (see models/claim).
    superseded: bool
