"""FalkorDB (de)serialization for `:Claim` nodes (the reified fact model).

Centralizes the flatten/inflate between a `FactClaim` pydantic model and the
scalar/JSON-string node properties FalkorDB stores. Lists and nested structures
are JSON-encoded into `*_json` string properties, matching the convention the
entity/relation serialization in falkordb_store.py already uses (FalkorDB node
properties must be scalars or arrays of scalars, not nested maps).
"""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from contextstore.models.claim import Claim
from contextstore.models.fact_claim import ClaimStatus, FactClaim
from contextstore.models.scope import Scope


def _claims_to_json(claims: list[Claim]) -> str:
    return json.dumps([claim.model_dump(mode="json") for claim in claims])


def _claims_from_json(raw: str) -> list[Claim]:
    return [Claim.model_validate(item) for item in json.loads(raw)]


def claim_to_node_props(claim: FactClaim, memory_id: str) -> dict[str, Any]:
    """Flatten a FactClaim into `:Claim` node properties. `valid_to` is omitted
    when None (FalkorDB has no first-class null; absence reads back as None)."""
    props: dict[str, Any] = {
        "id": str(claim.id),
        "predicate": claim.predicate,
        "raw_predicate": claim.raw_predicate,
        "subject_id": str(claim.subject_id),
        "object_id": str(claim.object_id),
        "status": claim.status,
        "asserted_by_json": json.dumps(claim.asserted_by),
        "support_count": claim.support_count,
        "confidence": claim.confidence,
        "valid_from": claim.valid_from.isoformat(),
        "supersedes_json": json.dumps([str(cid) for cid in claim.supersedes]),
        "disputed_with_json": json.dumps([str(cid) for cid in claim.disputed_with]),
        "created_at": claim.created_at.isoformat(),
        "last_seen": claim.last_seen.isoformat(),
        "properties_json": json.dumps(claim.properties),
        "claims_json": _claims_to_json(claim.claims),
        "scope_json": json.dumps(claim.scope.to_query_dict()),
        "memory_id": memory_id,
    }
    if claim.valid_to is not None:
        props["valid_to"] = claim.valid_to.isoformat()
    return props


def node_to_claim(properties: dict[str, Any]) -> FactClaim:
    """Inflate `:Claim` node properties back into a FactClaim."""
    valid_to_raw = properties.get("valid_to")
    status: ClaimStatus = properties["status"]
    return FactClaim(
        id=UUID(properties["id"]),
        predicate=properties["predicate"],
        raw_predicate=properties["raw_predicate"],
        subject_id=UUID(properties["subject_id"]),
        object_id=UUID(properties["object_id"]),
        status=status,
        asserted_by=json.loads(properties.get("asserted_by_json", "[]")),
        support_count=int(properties.get("support_count", 1)),
        confidence=float(properties.get("confidence", 1.0)),
        valid_from=datetime.fromisoformat(properties["valid_from"]),
        valid_to=datetime.fromisoformat(valid_to_raw) if valid_to_raw else None,
        supersedes=[UUID(cid) for cid in json.loads(properties.get("supersedes_json", "[]"))],
        disputed_with=[
            UUID(cid) for cid in json.loads(properties.get("disputed_with_json", "[]"))
        ],
        created_at=datetime.fromisoformat(properties["created_at"]),
        last_seen=datetime.fromisoformat(properties["last_seen"]),
        properties=json.loads(properties.get("properties_json", "{}")),
        claims=_claims_from_json(properties.get("claims_json", "[]")),
        scope=Scope.from_dict(json.loads(properties["scope_json"])),
    )
