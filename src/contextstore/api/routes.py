"""v1 API routes: write (remember), read (recall), graph snapshot, and the
operator-only key-management endpoints.

tenant_id is never accepted from a request body or query param: it comes from
the authenticated API key (see api/auth.py) and is merged into the Scope
server-side. Callers may still pass *other* scope keys (user_id, project, ...)
via `extra_scope`, which are used for in-tenant filtering downstream
(Scope.includes); any `tenant_id` smuggled into `extra_scope` is dropped.
"""

import re
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from contextstore.api.auth import AuthContext, DbDep, require_admin, require_api_key
from contextstore.api.dependencies import EmbeddingProviderDep, GraphStoreDep
from contextstore.api.ratelimit import require_memories_quota, require_recall_quota
from contextstore.core.service import recall as recall_service
from contextstore.core.service import remember as remember_service
from contextstore.db import postgres
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
    await postgres.log_usage(db, auth.api_key_id, scope.tenant_id, "/v1/recall")
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

    traversal_results = await graph_store.traverse([entity.id for entity in entities], 1, scope)
    relations_by_id = {
        relation.id: relation for _, relations in traversal_results for relation in relations
    }
    return GraphSnapshot(entities=entities, relations=list(relations_by_id.values()))


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
) -> list[AgentResponse]:
    rows = await postgres.list_agents(db, auth.tenant_id)
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
) -> list[ProjectResponse]:
    """List the authenticated user's own projects (across all their keys)."""
    rows = await postgres.list_projects_for_user(db, auth.user_id)
    return [ProjectResponse(**row) for row in rows]
