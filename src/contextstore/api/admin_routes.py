"""Operator admin API: cross-tenant inspection and destructive controls.

This namespace is the operator's window across *all* tenants -- the thing that
previously required SSH + raw Cypher or direct Postgres. It is completely
separate from regular user auth: every route here depends on `require_admin`
(the shared ADMIN_TOKEN bearer), never on a user's API key, and routes address
any tenant's graph directly by `tenant_id` rather than the caller's own scope.

Read endpoints assemble from data that already exists -- Postgres rows
(projects/users/usage/memory_writes) and the per-tenant FalkorDB graph (stats,
full snapshot, an entity's full claim history). Write endpoints are destructive
and deliberately explicit: deleting one audit row does NOT touch the graph, and
wiping a tenant requires a typed confirmation and is logged loudly.
"""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from contextstore.api.auth import DbDep, require_admin
from contextstore.api.dependencies import GraphStoreDep
from contextstore.api.routes import GraphSnapshot
from contextstore.db import postgres
from contextstore.models.claim import Claim
from contextstore.models.scope import Scope

logger = structlog.get_logger()

# Every route in this router requires the admin token; no per-route repetition.
router = APIRouter(prefix="/v1/admin", dependencies=[Depends(require_admin)])


# --- Read: users & projects --------------------------------------------------


class AdminUser(BaseModel):
    id: UUID
    email: str
    created_at: datetime
    project_count: int


@router.get("/users", response_model=list[AdminUser])
async def list_users(db: DbDep) -> list[AdminUser]:
    """All users with a count of the projects they own."""
    rows = await postgres.list_users_with_project_counts(db)
    return [AdminUser(**row) for row in rows]


class AdminProject(BaseModel):
    id: UUID
    tenant_id: str
    name: str
    description: str | None
    created_at: datetime
    owner_user_id: UUID
    owner_email: str
    last_activity_at: datetime | None
    # Live per-tenant graph stats, queried from FalkorDB at request time.
    node_count: int
    edge_count: int


async def _project_with_stats(row: dict[str, Any], graph_store: GraphStoreDep) -> AdminProject:
    node_count, edge_count = await graph_store.graph_stats(row["tenant_id"])
    return AdminProject(**row, node_count=node_count, edge_count=edge_count)


@router.get("/projects", response_model=list[AdminProject])
async def list_projects(db: DbDep, graph_store: GraphStoreDep) -> list[AdminProject]:
    """Every project across all users, each enriched with live FalkorDB
    node/edge counts and a last-activity timestamp from usage_log."""
    rows = await postgres.list_all_projects(db)
    return list(await asyncio.gather(*(_project_with_stats(row, graph_store) for row in rows)))


# --- Read: a single project's raw memory writes & graph ----------------------


class AdminMemoryWrite(BaseModel):
    id: UUID
    tenant_id: str
    source: str
    raw_content: str
    extracted_entity_count: int
    extracted_relation_count: int
    created_at: datetime


@router.get("/projects/{tenant_id}/memories", response_model=list[AdminMemoryWrite])
async def list_project_memories(
    tenant_id: str, db: DbDep, limit: int = Query(default=100, ge=1, le=1000)
) -> list[AdminMemoryWrite]:
    """Recent raw memory writes for a tenant from the audit log -- the original
    submitted content alongside what extraction pulled out of it."""
    rows = await postgres.list_memory_writes(db, tenant_id, limit)
    return [AdminMemoryWrite(**row) for row in rows]


@router.get("/projects/{tenant_id}/graph", response_model=GraphSnapshot)
async def get_project_graph(tenant_id: str, graph_store: GraphStoreDep) -> GraphSnapshot:
    """Full graph snapshot for any tenant. Same assembly as the user-facing
    GET /v1/graph (find_entities + a 1-hop traverse), but scoped to an arbitrary
    tenant rather than the caller's own."""
    scope = Scope.from_dict({"tenant_id": tenant_id})
    entities = await graph_store.find_entities(scope)
    if not entities:
        return GraphSnapshot()
    traversal_results = await graph_store.traverse([entity.id for entity in entities], 1, scope)
    relations_by_id = {
        relation.id: relation for _, relations in traversal_results for relation in relations
    }
    return GraphSnapshot(entities=entities, relations=list(relations_by_id.values()))


# --- Read: full claim history for one entity (provenance inspection) ---------


class AnnotatedClaim(BaseModel):
    """One claim from an entity's history, with a `superseded` flag derived from
    whether any later claim's provenance lists this claim's id in `supersedes`."""

    claim: Claim
    superseded: bool


class EntityClaimsResponse(BaseModel):
    entity_id: UUID
    entity_name: str
    entity_type: str
    # Every claim ever made about the entity, oldest first, each flagged as
    # active or superseded -- the ground-truth provenance view, not just the
    # active value.
    claims: list[AnnotatedClaim] = Field(default_factory=list)


def _superseded_claim_ids(claims: list[Claim]) -> set[UUID]:
    """Ids of claims marked superseded by some other claim's provenance."""
    return {UUID(claim_id) for claim in claims for claim_id in (claim.provenance.supersedes or [])}


@router.get(
    "/projects/{tenant_id}/entities/{entity_id}/claims",
    response_model=EntityClaimsResponse,
)
async def get_entity_claims(
    tenant_id: str, entity_id: UUID, graph_store: GraphStoreDep
) -> EntityClaimsResponse:
    """Full claim history for one entity in any tenant: every claim ever made,
    which source asserted it, and which claims were superseded, oldest first.
    The history is already persisted on the node (claims_json); this just reads
    it back and annotates supersession -- no new graph plumbing."""
    entity = await graph_store.get_entity(entity_id, tenant_id)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found in this tenant's graph.",
        )
    superseded = _superseded_claim_ids(entity.claims)
    ordered = sorted(entity.claims, key=lambda claim: claim.provenance.created_at)
    return EntityClaimsResponse(
        entity_id=entity.id,
        entity_name=entity.name,
        entity_type=entity.entity_type,
        claims=[
            AnnotatedClaim(claim=claim, superseded=claim.id in superseded) for claim in ordered
        ],
    )


# --- Read: usage across all tenants ------------------------------------------


class AdminUsageRow(BaseModel):
    id: UUID
    api_key_id: UUID
    tenant_id: str
    endpoint: str
    tokens_used: int | None
    created_at: datetime


@router.get("/usage", response_model=list[AdminUsageRow])
async def list_usage(
    db: DbDep,
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
) -> list[AdminUsageRow]:
    """Usage-log rows across all tenants (or one, via `tenant_id`), newest
    first, with token counts and endpoint for cost breakdowns."""
    rows = await postgres.list_usage(db, tenant_id, limit)
    return [AdminUsageRow(**row) for row in rows]


# --- Destructive: delete one audit row, wipe a tenant, revoke any key --------


@router.delete(
    "/projects/{tenant_id}/memories/{memory_write_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project_memory(tenant_id: str, memory_write_id: UUID, db: DbDep) -> None:
    """Hard-delete one audit-log entry for a tenant.

    NOTE: this removes only the audit record of the submission. It does NOT
    retroactively un-write the graph -- the entities/relations that this memory
    contributed remain, because un-writing a single memory's graph effects
    (shared entities across writes) is a separate, harder problem and is out of
    scope here.
    """
    deleted = await postgres.delete_memory_write(db, tenant_id, memory_write_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory-write audit entry not found for this tenant.",
        )


@router.delete("/projects/{tenant_id}", status_code=status.HTTP_200_OK)
async def wipe_project(
    tenant_id: str,
    db: DbDep,
    graph_store: GraphStoreDep,
    confirm: str = Query(
        default="",
        description="Must equal the tenant_id being wiped, as a deliberate confirmation.",
    ),
) -> dict[str, str]:
    """DESTRUCTIVE: wipe a tenant's entire FalkorDB graph and all its Postgres
    rows (project, api_keys, agents, usage_log, memory_writes).

    Requires `?confirm=<tenant_id>` to match exactly -- a guard against an
    accidental wipe from a mistyped path. Logged loudly. The graph drop happens
    after the Postgres rows are gone so a half-done wipe leaves no usable key
    pointing at an emptied graph.
    """
    if confirm != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation required: pass ?confirm=<tenant_id> matching the path.",
        )

    project = await postgres.get_project_by_tenant(db, tenant_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    logger.warning(
        "admin.wipe_project.start",
        tenant_id=tenant_id,
        project_id=str(project["id"]),
        owner_user_id=str(project["owner_user_id"]),
    )
    deleted = await postgres.delete_project_cascade(db, tenant_id)
    await graph_store.drop_graph(tenant_id)
    logger.warning("admin.wipe_project.done", tenant_id=tenant_id, postgres_deleted=deleted)
    return {"tenant_id": tenant_id, "status": "wiped"}


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_any_key(key_id: UUID, db: DbDep) -> None:
    """Admin override: revoke any API key regardless of which tenant owns it
    (the self-service DELETE /v1/keys is constrained to the caller's tenant)."""
    revoked = await postgres.revoke_api_key(db, key_id)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found or already revoked.",
        )
