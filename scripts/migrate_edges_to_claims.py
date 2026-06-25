"""Migrate a tenant's legacy direct-edge facts to the reified-claim model.

Old model: a fact was a typed edge `(a:Entity)-[:PREDICATE]->(b:Entity)` with
properties (id, claims_json, properties_json, provenance_json,
contributing_sources_json, support_count, last_seen, scope_json, memory_id).

New model: a fact is a `:Claim` node linked by `:SUBJECT`/`:OBJECT` edges. This
script reads each legacy edge, builds an equivalent active FactClaim (preserving
id, property-level claim history, provenance, support, scope), upserts it, and
deletes the old edge. In-place and migratable -- no rebuild.

Accepted limitation: migration does NOT retro-adjudicate. Every migrated fact
becomes `active`; any pre-existing conflicting edges become parallel active
claims and are only reconciled when next asserted via remember().

Usage:
    uv run python scripts/migrate_edges_to_claims.py <tenant_id> [<tenant_id> ...]
    uv run python scripts/migrate_edges_to_claims.py --all
"""

import asyncio
import json
import sys
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from falkordb.asyncio.graph import AsyncGraph

from contextstore.core.config import get_settings
from contextstore.graph.falkordb_store import FalkorDBGraphStore
from contextstore.models.claim import Claim
from contextstore.models.fact_claim import FactClaim
from contextstore.models.provenance import Provenance
from contextstore.models.scope import Scope

logger = structlog.get_logger()

# Legacy direct edges only (Claim structural edges are SUBJECT/OBJECT). At
# migration time no Claim nodes exist yet, but excluding them keeps a re-run safe.
_READ_LEGACY_EDGES = """
MATCH (a:Entity)-[r]->(b:Entity)
WHERE type(r) <> 'SUBJECT' AND type(r) <> 'OBJECT'
RETURN type(r) AS predicate, r AS rel, a.id AS subject_id, b.id AS object_id
"""

_DELETE_LEGACY_EDGE = """
MATCH (a:Entity {id: $subject_id})-[r]->(b:Entity {id: $object_id})
WHERE id(r) = $edge_internal_id
DELETE r
"""


def _claims_from_json(raw: str) -> list[Claim]:
    return [Claim.model_validate(item) for item in json.loads(raw or "[]")]


def _legacy_edge_to_claim(
    predicate: str, props: dict[str, Any], subject_id: str, object_id: str
) -> FactClaim:
    provenance = (
        Provenance.model_validate_json(props["provenance_json"])
        if props.get("provenance_json")
        else Provenance(source="migration")
    )
    contributing = json.loads(props.get("contributing_sources_json", "[]")) or [provenance.source]
    last_seen = props.get("last_seen")
    valid_from = datetime.fromisoformat(last_seen) if last_seen else provenance.created_at
    return FactClaim(
        id=UUID(props["id"]) if props.get("id") else uuid4(),
        predicate=predicate,
        raw_predicate=predicate,
        subject_id=UUID(subject_id),
        object_id=UUID(object_id),
        status="active",
        asserted_by=contributing,
        support_count=int(props.get("support_count", 1)),
        confidence=provenance.confidence,
        valid_from=valid_from,
        properties=json.loads(props.get("properties_json", "{}")),
        claims=_claims_from_json(props.get("claims_json", "[]")),
        scope=Scope.from_dict(json.loads(props["scope_json"])),
    )


async def migrate_tenant(store: FalkorDBGraphStore, tenant_id: str) -> int:
    """Migrate every legacy direct edge in a tenant's graph to a :Claim node.
    Returns the number of claims created."""
    graph: AsyncGraph = store._graph_for(tenant_id)
    result = await graph.query(_READ_LEGACY_EDGES)
    migrated = 0
    for predicate, rel, subject_id, object_id in result.result_set:
        claim = _legacy_edge_to_claim(predicate, rel.properties, subject_id, object_id)
        memory_id = rel.properties.get("memory_id", "")
        await store.upsert_claim(claim, memory_id)
        await graph.query(
            _DELETE_LEGACY_EDGE,
            {"subject_id": subject_id, "object_id": object_id, "edge_internal_id": rel.id},
        )
        migrated += 1
    logger.info("migrate_tenant.done", tenant_id=tenant_id, claims_created=migrated)
    return migrated


async def _main(tenant_ids: list[str]) -> None:
    settings = get_settings()
    store = FalkorDBGraphStore(
        host=settings.falkordb_host,
        port=settings.falkordb_port,
        password=(
            settings.falkordb_password.get_secret_value() if settings.falkordb_password else None
        ),
    )
    try:
        if tenant_ids == ["--all"]:
            graphs = await store._client.list_graphs()
            tenant_ids = [g.removeprefix("tenant_") for g in graphs if g.startswith("tenant_")]
        total = 0
        for tenant_id in tenant_ids:
            total += await migrate_tenant(store, tenant_id)
        logger.info("migrate.complete", tenants=len(tenant_ids), claims_created=total)
    finally:
        await store.aclose()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    asyncio.run(_main(sys.argv[1:]))
