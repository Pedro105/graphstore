"""Abstract interface for graph-backed persistence of memories, entities, and relations."""

from abc import ABC, abstractmethod
from uuid import UUID

from contextstore.models.entity import Entity
from contextstore.models.fact import Fact
from contextstore.models.fact_claim import FactClaim
from contextstore.models.memory import Memory
from contextstore.models.relation import Relation
from contextstore.models.scope import Scope


class GraphStore(ABC):
    """Persists memories as entities and relations in a property graph.

    Concrete implementations are confined to `graph/`; callers elsewhere
    interact only through this interface and `models/` types.

    Every tenant gets a structurally separate graph (see
    `ensure_graph_initialized`), since vector search can't be combined with
    property filters reliably enough to enforce tenant isolation by
    filtering alone. `get_entity` and `delete_memory` take `tenant_id`
    directly (rather than a full `Scope`) because they address a single
    known id and only need to know which graph to look in.
    """

    @abstractmethod
    async def ensure_graph_initialized(self, tenant_id: str, embedding_dimension: int) -> None:
        """Ensure the tenant's graph exists and has its vector index set up.

        Idempotent: safe to call on every write.
        """

    @abstractmethod
    async def write_memory(self, memory: Memory) -> str:
        """Persist a memory's entities (MERGE by id). Returns the memory id.

        Relations are NOT written here in the reified-claim model -- facts are
        persisted as `:Claim` nodes via `upsert_claim`, after adjudication
        (resolution/conflict_resolver.py) decides their status. The orchestrating
        service writes entities first (so claim edges have endpoints), then
        adjudicates and upserts each claim.
        """

    @abstractmethod
    async def find_active_claims(
        self, scope: Scope, subject_id: UUID, predicate: str
    ) -> list[FactClaim]:
        """Active `:Claim` nodes with this subject and normalized predicate, in
        `scope`'s tenant -- the conflict/corroboration candidates the adjudicator
        weighs a new assertion against."""

    @abstractmethod
    async def upsert_claim(self, claim: FactClaim, memory_id: str) -> None:
        """Create-or-update a `:Claim` node by id (status transitions reuse this)
        and ensure its `:SUBJECT`/`:OBJECT` edges exist. Idempotent on the edges."""

    @abstractmethod
    async def project_display_edges(self, scope: Scope) -> list[Relation]:
        """Every live (active/disputed) claim in `scope`'s tenant, collapsed into
        display-edge `Relation`s. The single projection both GET /v1/graph and the
        traversal path consume -- superseded/retracted claims are excluded."""

    @abstractmethod
    async def find_predicates(self, scope: Scope) -> list[str]:
        """Distinct raw predicates across the tenant's live claims (extraction
        vocabulary bias). Replaces the old traverse-based relation-type scan."""

    @abstractmethod
    async def get_entity(self, entity_id: UUID, tenant_id: str) -> Entity | None:
        """Fetch a single entity by id, or None if it doesn't exist."""

    @abstractmethod
    async def find_entities(
        self,
        scope: Scope,
        name: str | None = None,
        entity_type: str | None = None,
    ) -> list[Entity]:
        """Find entities visible within `scope`, optionally filtered by name/type."""

    @abstractmethod
    async def find_similar_entities(
        self,
        scope: Scope,
        embedding: list[float],
        entity_type: str | None,
        k: int,
    ) -> list[tuple[Entity, float]]:
        """Vector search for entities near `embedding` within `scope`'s tenant.

        Returns (entity, similarity) pairs, most similar first, where
        similarity is in [0, 1] with 1 meaning identical (this is FalkorDB's
        cosine distance converted to similarity — see falkordb_store.py).
        Filtered to `entity_type` and `Scope.includes` in Python after the
        vector search, since FalkorDB vector queries don't combine well
        with property filters.
        """

    @abstractmethod
    async def find_by_fulltext(
        self,
        scope: Scope,
        query_text: str,
        limit: int,
    ) -> list[tuple[UUID, int]]:
        """Full-text search for entities whose name matches `query_text`,
        within `scope`'s tenant.

        Returns (entity_id, rank) pairs, best match first (rank 1 = best),
        up to `limit` entities, filtered to `Scope.includes` in Python
        after the search (same pragmatic simplification as
        `find_similar_entities`). Returns an empty list -- never raises --
        if the tenant's full-text index doesn't exist yet or `query_text`
        sanitizes down to nothing.
        """

    @abstractmethod
    async def traverse_from_seeds(
        self,
        scope: Scope,
        seed_ids: list[str],
        depth: int,
        max_entities: int = 200,
    ) -> tuple[list[Entity], list[Relation], bool]:
        """Breadth-first multi-hop expansion from `seed_ids`, up to `depth`
        hops, within `scope`'s tenant.

        Returns the reachable subgraph as (entities, relations, truncated):
        the seeds plus every entity reachable within `depth` undirected hops,
        the relations among the returned entities, and a `truncated` flag set
        True when the `max_entities` cap stopped expansion early (entity
        count is then <= `max_entities`). This is the iterative-BFS traversal
        used by the recall path; the older `traverse` remains for the
        remember path and graph snapshot.
        """

    @abstractmethod
    async def delete_memory(self, memory_id: str, tenant_id: str) -> bool:
        """Delete everything written by a given memory. Returns True if anything was deleted."""

    @abstractmethod
    async def delete_entity(self, entity_id: UUID, tenant_id: str) -> bool:
        """Hard-delete a single entity (and its incident relations) by id.

        Addresses a tenant directly by id (like `get_entity`/`delete_memory`),
        since it targets one known node. DETACH-deletes the node so its edges
        go with it. Returns True if a node was deleted, False if no entity with
        that id exists in the tenant's graph (the caller turns that into a 404).
        Tenant-scoped by construction: an id belonging to another tenant isn't
        in this tenant's graph, so it deletes nothing and returns False.
        """

    @abstractmethod
    async def graph_stats(self, tenant_id: str) -> tuple[int, int]:
        """Return (entity_count, relation_count) for a tenant's graph.

        Addresses a tenant directly by id (like `get_entity`/`delete_memory`),
        for the operator admin view's per-project live stats. Returns (0, 0)
        for a tenant whose graph has never been written to.
        """

    @abstractmethod
    async def fetch_entity_claims_page(
        self, tenant_id: str, offset: int, limit: int
    ) -> tuple[list[Fact], int]:
        """One page of flattened entity claims for a tenant, plus the tenant's
        total :Entity node count (for the pager).

        Pagination is at the *node* level (`ORDER BY id SKIP/LIMIT`), so only one
        page of nodes is ever materialized -- the whole graph is never loaded.
        Each node's `claims_json` is expanded to one Fact per claim. Returns
        ([], 0) for a tenant whose graph was never created. Powers the operator
        facts table (api/admin_routes.py)."""

    @abstractmethod
    async def drop_graph(self, tenant_id: str) -> None:
        """Delete a tenant's entire graph (all entities, relations, indices).

        Destructive and not scoped -- used only by the operator admin "wipe
        tenant" path. Idempotent: dropping an already-empty/absent graph is a
        no-op, not an error.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the underlying graph store is reachable."""
