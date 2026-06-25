"""v1 API routes: write (remember), read (recall), graph snapshot, and the
operator-only key-management endpoints.

tenant_id is never accepted from a request body or query param: it comes from
the authenticated API key (see api/auth.py) and is merged into the Scope
server-side. Callers may still pass *other* scope keys (user_id, project, ...)
via `extra_scope`, which are used for in-tenant filtering downstream
(Scope.includes); any `tenant_id` smuggled into `extra_scope` is dropped.
"""

import asyncio
import re
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from contextstore.api.auth import AuthContext, DbDep, require_admin, require_api_key
from contextstore.api.dependencies import EmbeddingProviderDep, GraphStoreDep
from contextstore.api.pagination import PaginationDep
from contextstore.api.ratelimit import require_memories_quota, require_recall_quota
from contextstore.core.service import recall as recall_service
from contextstore.core.service import remember as remember_service
from contextstore.db import postgres
from contextstore.models.claim import Claim
from contextstore.models.entity import Entity
from contextstore.models.memory import Memory
from contextstore.models.recall import RecallResult, RetrievalMode
from contextstore.models.relation import Relation
from contextstore.models.scope import Scope, ScopeValue

router = APIRouter(prefix="/v1")

# Same charset Scope enforces on tenant_id (it's used as a FalkorDB graph name).
_SAFE_TENANT_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _scope_from_auth(auth: AuthContext, extra_scope: dict[str, ScopeValue]) -> Scope:
    """Build the Scope for a request: tenant_id is authoritative from the API
    key; any other keys the caller supplied are layered on. A `tenant_id` in
    `extra_scope` is ignored -- the caller does not get to choose its tenant."""
    merged: dict[str, ScopeValue] = {k: v for k, v in extra_scope.items() if k != "tenant_id"}
    merged["tenant_id"] = auth.tenant_id
    return Scope.from_dict(merged)


class RememberRequest(BaseModel):
    content: str = Field(min_length=1)
    source: str = Field(min_length=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: list[str] | None = None
    extra_scope: dict[str, ScopeValue] = Field(
        default_factory=dict,
        description=(
            "Optional non-tenant scope keys (e.g. user_id, project, agent_id) "
            "to file this memory under. tenant_id is derived from the API key "
            "and cannot be set here."
        ),
    )


class RecallRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(
        default=10,
        description=(
            "Maximum number of seed entities returned from the seed step "
            "(vector similarity, full-text, or both fused -- see "
            "retrieval_mode). Traversal results from these seeds are not "
            "subject to this limit, so the response may contain more than "
            "`limit` entities once one-hop neighbours are included."
        ),
    )
    traversal_depth: int | None = Field(
        default=None,
        description=(
            "Hops to traverse from the seed entities. Leave unset to let the "
            "query classifier choose (depth 1 for exact-lookup/single-hop "
            "queries, depth 2 for relational ones). Setting this -- or "
            "retrieval_mode -- pins routing and skips the classifier."
        ),
    )
    retrieval_mode: RetrievalMode | None = Field(
        default=None,
        description=(
            "How to seed entities before traversal: 'vector' (similarity "
            "search only), 'fulltext' (keyword search only), or 'hybrid' "
            "(both, fused via reciprocal rank fusion). Leave unset to let the "
            "query classifier choose. Setting this -- or traversal_depth -- "
            "pins routing and skips the classifier."
        ),
    )
    max_entities: int = Field(
        default=200,
        ge=1,
        description=(
            "Hard cap on the total number of entities the multi-hop "
            "traversal will accumulate. If expansion would exceed this, the "
            "subgraph is truncated and RecallResult.truncated is set True."
        ),
    )
    synthesise: bool = Field(
        default=False,
        description=(
            "When true, generate a natural-language answer from the retrieved "
            "subgraph and return it as RecallResult.synthesis. Additive: the "
            "structured entities/relations are always returned regardless. "
            "Synthesis failures degrade to structured-only output rather than "
            "failing the request."
        ),
    )
    extra_scope: dict[str, ScopeValue] = Field(
        default_factory=dict,
        description=(
            "Optional non-tenant scope keys (e.g. user_id, project) to narrow "
            "the search. tenant_id is derived from the API key and cannot be "
            "set here."
        ),
    )


@router.post("/memories", response_model=Memory)
async def create_memory(
    body: RememberRequest,
    graph_store: GraphStoreDep,
    embedding_provider: EmbeddingProviderDep,
    db: DbDep,
    auth: Annotated[AuthContext, Depends(require_memories_quota)],
) -> Memory:
    scope = _scope_from_auth(auth, body.extra_scope)
    memory, tokens_used = await remember_service(
        content=body.content,
        scope=scope,
        source=body.source,
        graph_store=graph_store,
        embedding_provider=embedding_provider,
        confidence=body.confidence,
        evidence=body.evidence,
    )
    # Audit log of the raw submission, decoupled from the graph write: the graph
    # engine discards `content` after extraction, so this Postgres row is the
    # only record of what was actually submitted vs. what got extracted. Both
    # calls are best-effort and never fail the request.
    await postgres.record_memory_write(
        db,
        scope.tenant_id,
        body.source,
        body.content,
        len(memory.entities),
        len(memory.relations),
    )
    await postgres.log_usage(
        db, auth.api_key_id, scope.tenant_id, "/v1/memories", tokens_used=tokens_used
    )
    return memory


@router.post("/recall", response_model=RecallResult)
async def recall_memories(
    body: RecallRequest,
    graph_store: GraphStoreDep,
    embedding_provider: EmbeddingProviderDep,
    db: DbDep,
    auth: Annotated[AuthContext, Depends(require_recall_quota)],
) -> RecallResult:
    scope = _scope_from_auth(auth, body.extra_scope)
    result = await recall_service(
        query=body.query,
        scope=scope,
        graph_store=graph_store,
        embedding_provider=embedding_provider,
        limit=body.limit,
        traversal_depth=body.traversal_depth,
        retrieval_mode=body.retrieval_mode,
        max_entities=body.max_entities,
        synthesise=body.synthesise,
    )
    # Persist recall latency + the chosen query class (RetrievalStats is
    # otherwise discarded after the response) so the admin analytics view can
    # show p50/p95 latency trends and query-class breakdowns over time.
    await postgres.log_usage(
        db,
        auth.api_key_id,
        scope.tenant_id,
        "/v1/recall",
        latency_ms=round(result.stats.total_ms),
        query_class=result.stats.query_class,
    )
    return result


class GraphSnapshot(BaseModel):
    """Read-only view of a tenant's full graph, for visualization clients.

    Not a domain model (doesn't live in models/) -- it's just an aggregate
    of existing Entity/Relation reads, assembled below from GraphStore
    methods that already exist (find_entities, traverse). No new store
    method or Cypher was added for this.
    """

    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)


@router.get("/graph", response_model=GraphSnapshot)
async def get_graph(
    graph_store: GraphStoreDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
) -> GraphSnapshot:
    scope = Scope.from_dict({"tenant_id": auth.tenant_id})
    entities = await graph_store.find_entities(scope)
    if not entities:
        return GraphSnapshot()

    relations = await graph_store.project_display_edges(scope)
    return GraphSnapshot(entities=entities, relations=relations)


# --- Observability: tenant-scoped analytics, activity feed & per-agent sources
#
# These three read endpoints surface, for the *caller's own tenant*, the data
# the engine already records in Postgres (usage_log, memory_writes). They mirror
# the operator admin analytics (api/admin_routes.py) but are scoped to one
# tenant via the API key rather than spanning all of them, so the dashboard can
# show write/recall trends, latency, and which agent wrote what -- without the
# admin token. No new tables or graph plumbing: same postgres aggregates, with a
# tenant filter applied.


class WritePoint(BaseModel):
    day: date
    count: int


class TokenPoint(BaseModel):
    day: date
    tokens: int


class LatencyPoint(BaseModel):
    day: date
    count: int
    p50: int | None
    p95: int | None


class ClassCount(BaseModel):
    query_class: str
    count: int


class AnalyticsResponse(BaseModel):
    """The caller tenant's write/token/latency time series plus its recall
    query-class mix -- everything the Overview charts need in one round trip."""

    writes_over_time: list[WritePoint]
    tokens_over_time: list[TokenPoint]
    recall_latency: list[LatencyPoint]
    query_class_breakdown: list[ClassCount]


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    db: DbDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
    days: int = Query(default=30, ge=1, le=365),
    class_days: int = Query(default=7, ge=1, le=365),
) -> AnalyticsResponse:
    """Time-series analytics for the authenticated tenant: daily writes, token
    spend, and recall latency p50/p95 over `days`, plus the recall query-class
    breakdown over the last `class_days`. tenant_id comes from the API key."""
    tenant_id = auth.tenant_id
    writes, tokens, latency, classes = await asyncio.gather(
        postgres.writes_over_time(db, days, tenant_id),
        postgres.tokens_over_time(db, days, tenant_id),
        postgres.recall_latency_over_time(db, days, tenant_id),
        postgres.query_class_breakdown(db, class_days, tenant_id),
    )
    return AnalyticsResponse(
        writes_over_time=[WritePoint(**r) for r in writes],
        tokens_over_time=[TokenPoint(**r) for r in tokens],
        recall_latency=[LatencyPoint(**r) for r in latency],
        query_class_breakdown=[ClassCount(**r) for r in classes],
    )


class ActivityItem(BaseModel):
    """One recent write into the tenant's graph, from the memory_writes audit
    log: which source (agent) wrote, the submitted content, and how many
    entities/relations extraction pulled out of it."""

    id: UUID
    source: str
    raw_content: str
    extracted_entity_count: int
    extracted_relation_count: int
    created_at: datetime


@router.get("/activity", response_model=list[ActivityItem])
async def list_activity(
    db: DbDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ActivityItem]:
    """Recent writes into the authenticated tenant's graph, newest first -- the
    'who wrote what, when' activity feed. Reads the memory_writes audit log
    scoped to the caller's tenant."""
    rows = await postgres.list_memory_writes(db, auth.tenant_id, limit)
    return [ActivityItem(**row) for row in rows]


class SourceActivity(BaseModel):
    """Per-source (per-agent) write breakdown for the tenant: how many writes,
    total entities/relations contributed, and when it last wrote."""

    source: str
    write_count: int
    entities: int
    relations: int
    last_activity_at: datetime


@router.get("/sources", response_model=list[SourceActivity])
async def list_sources(
    db: DbDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
) -> list[SourceActivity]:
    """Per-agent contribution for the authenticated tenant, busiest first: which
    sources wrote, how much each, and when each last wrote. The multi-agent
    coordination view, scoped to the caller's own project."""
    rows = await postgres.project_sources(db, auth.tenant_id)
    return [SourceActivity(**row) for row in rows]


# --- Provenance: full claim history for one of the caller's own entities ------
#
# The same inspection the operator admin API offers cross-tenant
# (api/admin_routes.py's get_entity_claims), but scoped to the caller's own
# tenant via the API key rather than addressing an arbitrary tenant by path. A
# user is entitled to see who asserted what in *their own* graph, so this needs
# no admin token. Reuses graph_store.get_entity + the claim history already
# persisted on the node -- no new graph plumbing.


class AnnotatedClaim(BaseModel):
    """One claim from an entity's history, with a `superseded` flag derived from
    whether any later claim's provenance lists this claim's id in `supersedes`."""

    claim: Claim
    superseded: bool


class EntityClaimsResponse(BaseModel):
    entity_id: UUID
    entity_name: str
    entity_type: str
    # Every claim ever made about the entity, oldest first, each flagged active
    # or superseded -- the ground-truth provenance view, not just the active value.
    claims: list[AnnotatedClaim] = Field(default_factory=list)


def _superseded_claim_ids(claims: list[Claim]) -> set[UUID]:
    """Ids of claims marked superseded by some other claim's provenance."""
    return {UUID(claim_id) for claim in claims for claim_id in (claim.provenance.supersedes or [])}


@router.get("/entities/{entity_id}/claims", response_model=EntityClaimsResponse)
async def get_entity_claims(
    entity_id: UUID,
    graph_store: GraphStoreDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
) -> EntityClaimsResponse:
    """Full claim history for one entity in the authenticated tenant's graph:
    every claim ever made, which source asserted it, when, and which claims were
    superseded -- oldest first. The entity is looked up in the caller's own graph
    (tenant from the API key), so an entity id from another tenant is a 404, same
    as a nonexistent one."""
    entity = await graph_store.get_entity(entity_id, auth.tenant_id)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found in your graph.",
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


@router.delete("/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(
    entity_id: UUID,
    graph_store: GraphStoreDep,
    db: DbDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
) -> None:
    """Hard-delete one entity (and its incident relations) from the authenticated
    tenant's graph. Authorization is tenant-scoping only (the current model): any
    valid key may delete anything in its own tenant -- there is no inter-agent
    permission layer yet. The entity is addressed in the caller's own graph
    (tenant from the API key), so an id from another tenant is a 404, same as a
    nonexistent one. Irreversible: this removes the node and its edges outright
    (no supersession/history retained -- that's the separate soft-retract path)."""
    deleted = await graph_store.delete_entity(entity_id, auth.tenant_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found in your graph.",
        )
    # Best-effort usage record, consistent with the other authenticated endpoints;
    # never fails the delete.
    await postgres.log_usage(db, auth.api_key_id, auth.tenant_id, "/v1/entities")


# --- Usage monitoring: the caller tenant's current-month consumption ----------
#
# Everything the /dashboard/usage page needs in one round trip, scoped to the
# authenticated tenant. Reuses the same usage_log / memory_writes the rest of
# the observability surface reads -- no new tables.

# Placeholder token price for cost ESTIMATION only. Set to Anthropic's listed
# Claude Haiku input rate ($0.80 / million tokens) as a stand-in; usage_log
# records total tokens (not split input/output), so this is deliberately an
# estimate, surfaced as such in the UI. Update here when real pricing is wired.
_HAIKU_USD_PER_MTOK = 0.80


class UsageDayPoint(BaseModel):
    date: date
    recalls: int
    writes: int
    tokens: int


class EndpointUsage(BaseModel):
    calls: int
    tokens: int


class AgentUsage(BaseModel):
    source: str
    writes: int
    last_active: datetime


class UsageResponse(BaseModel):
    """Current-month usage for the authenticated tenant, plus a 30-day daily
    series and per-endpoint / per-agent breakdowns. `estimated_cost_usd` is an
    estimate from a placeholder token rate (see _HAIKU_USD_PER_MTOK)."""

    period: str  # "YYYY-MM" (UTC) of the totals below
    total_recalls: int
    total_writes: int
    tokens_used: int
    estimated_cost_usd: float
    by_day: list[UsageDayPoint]
    by_endpoint: dict[str, EndpointUsage]
    by_agent: list[AgentUsage]


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    db: DbDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
    days: int = Query(default=30, ge=1, le=90),
) -> UsageResponse:
    """Usage for the authenticated tenant: current-month recall/write/token
    totals with an estimated cost, a daily recalls/writes/tokens series over the
    last `days` days, and per-endpoint and per-agent breakdowns. Strictly scoped
    to the caller's tenant (from the API key). NULL token rows count as 0."""
    tenant_id = auth.tenant_id
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    writes, totals, endpoints, log_days, write_days, sources = await asyncio.gather(
        postgres.writes_since(db, tenant_id, month_start),
        postgres.usage_totals_since(db, tenant_id, month_start),
        postgres.usage_by_endpoint_since(db, tenant_id, month_start),
        postgres.usage_log_by_day(db, tenant_id, days),
        postgres.writes_over_time(db, days, tenant_id),
        postgres.project_sources(db, tenant_id),
    )

    # Both core endpoints are always present (zero when unused) so the cost table
    # has stable rows; a real zero, not invented data.
    by_endpoint: dict[str, EndpointUsage] = {
        "/v1/memories": EndpointUsage(calls=0, tokens=0),
        "/v1/recall": EndpointUsage(calls=0, tokens=0),
    }
    for row in endpoints:
        by_endpoint[row["endpoint"]] = EndpointUsage(calls=row["calls"], tokens=row["tokens"])

    # Merge recalls/tokens (usage_log) with writes (memory_writes) by day. Only
    # days with real activity appear -- no zero-filled phantom points.
    days_map: dict[date, UsageDayPoint] = {}
    for row in log_days:
        days_map[row["day"]] = UsageDayPoint(
            date=row["day"], recalls=row["recalls"], writes=0, tokens=row["tokens"]
        )
    for row in write_days:
        existing = days_map.get(row["day"])
        if existing is not None:
            existing.writes = row["count"]
        else:
            days_map[row["day"]] = UsageDayPoint(
                date=row["day"], recalls=0, writes=row["count"], tokens=0
            )
    by_day = [days_map[day] for day in sorted(days_map)]

    tokens_used = totals["tokens"]
    estimated_cost = round(tokens_used / 1_000_000 * _HAIKU_USD_PER_MTOK, 6)

    by_agent = [
        AgentUsage(
            source=row["source"], writes=row["write_count"], last_active=row["last_activity_at"]
        )
        for row in sources
    ]

    return UsageResponse(
        period=now.strftime("%Y-%m"),
        total_recalls=totals["recalls"],
        total_writes=writes,
        tokens_used=tokens_used,
        estimated_cost_usd=estimated_cost,
        by_day=by_day,
        by_endpoint=by_endpoint,
        by_agent=by_agent,
    )


# --- Key management: creation is operator-only (admin token); listing and
# --- revocation are tenant-scoped (the caller's own API key). ----------------


class CreateKeyRequest(BaseModel):
    user_id: UUID
    tenant_id: str = Field(min_length=1)
    name: str | None = None

    @field_validator("tenant_id")
    @classmethod
    def _safe_tenant_id(cls, value: str) -> str:
        if not _SAFE_TENANT_ID.match(value):
            raise ValueError("tenant_id must match ^[A-Za-z0-9_-]+$ (used as a graph name)")
        return value


class CreateKeyResponse(BaseModel):
    api_key: str
    api_key_id: UUID
    tenant_id: str
    note: str = "Store this key now; the plaintext is not retrievable later."


class ApiKeyResponse(BaseModel):
    """Safe view of an API key for the owning tenant -- never the hash or the
    raw key, which only ever exists at creation time."""

    id: UUID
    name: str | None
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


@router.post(
    "/keys",
    response_model=CreateKeyResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_key(body: CreateKeyRequest, db: DbDep) -> CreateKeyResponse:
    """Mint a key for a user/tenant. Admin-only: users can't issue their own
    keys yet (an operator does it for them)."""
    raw_key, api_key_id = await postgres.create_api_key(db, body.user_id, body.tenant_id, body.name)
    return CreateKeyResponse(api_key=raw_key, api_key_id=api_key_id, tenant_id=body.tenant_id)


@router.get("/keys", response_model=list[ApiKeyResponse])
async def list_keys(
    db: DbDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
) -> list[ApiKeyResponse]:
    """List the authenticated tenant's own keys (safe metadata only)."""
    rows = await postgres.list_api_keys(db, auth.tenant_id)
    return [ApiKeyResponse(**row) for row in rows]


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(
    key_id: UUID,
    db: DbDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
) -> None:
    """Revoke one of the authenticated tenant's own keys. Tenant-scoped (not
    admin): the lookup is constrained to keys owned by the caller's tenant, so
    a key from another tenant returns 404 rather than being revocable."""
    revoked = await postgres.revoke_api_key_for_tenant(db, key_id, auth.tenant_id)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found, already revoked, or not owned by this tenant.",
        )


# --- Agents (per-tenant registry of named writers) ---------------------------


class AgentCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class AgentResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime


@router.post("/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: AgentCreateRequest,
    db: DbDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
) -> AgentResponse:
    row = await postgres.create_agent(db, auth.tenant_id, body.name, body.description)
    return AgentResponse(**row)


@router.get("/agents", response_model=list[AgentResponse])
async def list_agents(
    db: DbDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
    page: PaginationDep,
) -> list[AgentResponse]:
    rows = await postgres.list_agents(db, auth.tenant_id, limit=page.limit, offset=page.offset)
    return [AgentResponse(**row) for row in rows]


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    db: DbDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
) -> None:
    deleted = await postgres.delete_agent(db, auth.tenant_id, agent_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found or not owned by this tenant.",
        )


# --- Projects: a user can own several separate graphs. Creation is
# --- self-service (any authenticated key) and mints a new key scoped to the
# --- new project's tenant, since a key is bound to exactly one tenant. --------


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class ProjectResponse(BaseModel):
    id: UUID
    tenant_id: str
    name: str
    description: str | None
    created_at: datetime


class ProjectCreateResponse(ProjectResponse):
    """A newly created project plus the API key minted for it. The key is the
    only time the plaintext exists -- it scopes future requests to this
    project's tenant/graph."""

    api_key: str
    api_key_id: UUID
    note: str = (
        "Store this key now; it scopes requests to this project and is not retrievable later."
    )


@router.post("/projects", response_model=ProjectCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreateRequest,
    db: DbDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
) -> ProjectCreateResponse:
    """Create a new project (a fresh tenant_id = its own FalkorDB graph) owned by
    the authenticated user, and mint an API key scoped to it. The owner is taken
    from the calling key, never the request body."""
    project, raw_key, api_key_id = await postgres.create_project_with_key(
        db, auth.user_id, body.name, body.description
    )
    return ProjectCreateResponse(**project, api_key=raw_key, api_key_id=api_key_id)


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    db: DbDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
    page: PaginationDep,
) -> list[ProjectResponse]:
    """List the authenticated user's own projects (across all their keys)."""
    rows = await postgres.list_projects_for_user(
        db, auth.user_id, limit=page.limit, offset=page.offset
    )
    return [ProjectResponse(**row) for row in rows]


class ProjectUpdateRequest(BaseModel):
    name: str = Field(min_length=1)


@router.patch("/projects/{tenant_id}", response_model=ProjectResponse)
async def rename_project(
    tenant_id: str,
    body: ProjectUpdateRequest,
    db: DbDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
) -> ProjectResponse:
    """Rename a project the authenticated user owns. Ownership is enforced in the
    UPDATE's WHERE clause (the user_id comes from the key, never the path/body),
    so a project the user doesn't own is a 404 -- same as if it didn't exist."""
    row = await postgres.rename_project_for_user(db, tenant_id, auth.user_id, body.name)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or not owned by the authenticated user.",
        )
    return ProjectResponse(**row)


@router.delete("/projects/{tenant_id}", status_code=status.HTTP_200_OK)
async def delete_project(
    tenant_id: str,
    db: DbDep,
    graph_store: GraphStoreDep,
    auth: Annotated[AuthContext, Depends(require_api_key)],
    confirm: str = Query(
        default="",
        description="Must equal the tenant_id being deleted, as a deliberate confirmation.",
    ),
) -> dict[str, str]:
    """DESTRUCTIVE: delete a project the authenticated user owns -- its FalkorDB
    graph and all its Postgres rows (project, api_keys, agents, usage_log,
    memory_writes). Mirrors the admin wipe, but scoped to the caller's own
    projects.

    Guards, in order: ownership (404 if the user doesn't own it), a typed
    `?confirm=<tenant_id>` match (400 otherwise), and a refusal to delete the
    very project the calling key is bound to (409) -- that would revoke the key
    mid-request and lock the user out of their own dashboard. The graph is
    dropped only after the Postgres rows are gone, so a partial failure never
    leaves a live key pointing at an emptied graph."""
    owned = await postgres.get_project_for_user(db, tenant_id, auth.user_id)
    if owned is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or not owned by the authenticated user.",
        )
    if confirm != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation required: pass ?confirm=<tenant_id> matching the path.",
        )
    if tenant_id == auth.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cannot delete the project your current API key is bound to. "
                "Switch to (or create) another project first."
            ),
        )
    await postgres.delete_project_cascade(db, tenant_id)
    await graph_store.drop_graph(tenant_id)
    return {"tenant_id": tenant_id, "status": "deleted"}
