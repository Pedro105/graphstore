"""Breadth-first multi-hop traversal over the knowledge graph.

The BFS bookkeeping -- frontier expansion hop by hop, visited-id tracking,
the `max_entities` hard cap, and the end-of-run relation filtering -- lives
here as a pure async function, decoupled from FalkorDB via two injected
fetch callables. `graph/falkordb_store.py`'s `traverse_from_seeds` supplies
the real Cypher-backed fetchers (one batched query per hop); tests supply
in-memory ones. Keeping the algorithm out of the store is what makes it
unit-testable without a live FalkorDB, and keeps the store responsible only
for Cypher.

Traversal is undirected (matches the existing one-hop `traverse`): a
neighbour reached over an incoming or outgoing edge is treated the same. A
relation's own `source_entity_id`/`target_entity_id` (from stored edge
properties) preserve the real direction regardless of which way it was
walked.
"""

from collections.abc import Awaitable, Callable
from uuid import UUID

import structlog

from contextstore.models.entity import Entity
from contextstore.models.relation import Relation

logger = structlog.get_logger()

# Fetch the seed Entity objects for the given ids (already scope-filtered by
# the caller). A seed with no matching/visible row is simply absent.
SeedFetcher = Callable[[list[str]], Awaitable[list[Entity]]]

# Fetch one hop out: every (neighbour, connecting_relation) pair for *all*
# edges incident to any frontier id -- including edges whose neighbour was
# already visited. Returning already-visited neighbours is deliberate: it's
# how edges *between* already-discovered entities (notably the seeds, which
# are all "visited" from the first hop) make it into the result. Without it,
# a recall whose seeds are interconnected returns those entities but none of
# the edges connecting them. Frontier expansion is decided separately by the
# BFS itself (an already-known neighbour is recorded but not re-expanded), so
# the fetcher does not need a visited set. A neighbour reachable by several
# edges yields several pairs; dedup happens here, not in the fetcher.
NeighbourFetcher = Callable[[list[str]], Awaitable[list[tuple[Entity, Relation]]]]


async def breadth_first_traverse(
    seed_ids: list[str],
    depth: int,
    max_entities: int,
    fetch_seeds: SeedFetcher,
    fetch_neighbours: NeighbourFetcher,
    *,
    tenant_id: str,
) -> tuple[list[Entity], list[Relation], bool]:
    """BFS up to `depth` hops from `seed_ids`, returning the reachable
    subgraph as (entities, relations, truncated).

    The seeds themselves are part of the returned subgraph (depth=1 from A
    returns {A} plus A's neighbours). `truncated` is True iff the
    `max_entities` cap stopped expansion before the graph or depth was
    exhausted; the returned entity count is then <= `max_entities`.
    Relations are filtered so both endpoints are present in the returned
    entity set.
    """
    if depth < 1:
        raise ValueError("depth must be >= 1")
    if max_entities < 1:
        raise ValueError("max_entities must be >= 1")

    entities_by_id: dict[str, Entity] = {}
    relations_by_id: dict[UUID, Relation] = {}
    truncated = False

    def _add_entity(entity: Entity) -> bool:
        """Add an entity if new and under the cap. Returns False (and flips
        `truncated`) if the cap is already reached, so callers can stop."""
        nonlocal truncated
        entity_id = str(entity.id)
        if entity_id in entities_by_id:
            return True
        if len(entities_by_id) >= max_entities:
            truncated = True
            return False
        entities_by_id[entity_id] = entity
        return True

    # Seeds first: they anchor the subgraph and form the initial frontier.
    frontier: list[str] = []
    for seed in await fetch_seeds(seed_ids):
        if _add_entity(seed):
            frontier.append(str(seed.id))
        else:
            break

    hops_completed = 0
    while frontier and hops_completed < depth and not truncated:
        rows = await fetch_neighbours(frontier)
        next_frontier: list[str] = []
        for neighbour, relation in rows:
            # Record every encountered edge; relations touching a neighbour
            # that ends up truncated away are dropped by the final filter.
            relations_by_id[relation.id] = relation
            neighbour_id = str(neighbour.id)
            already_known = neighbour_id in entities_by_id
            if not _add_entity(neighbour):
                break
            if not already_known:
                next_frontier.append(neighbour_id)
        frontier = next_frontier
        hops_completed += 1

    if truncated:
        logger.warning(
            "traversal.truncated",
            tenant_id=tenant_id,
            depth_reached=hops_completed,
            requested_depth=depth,
            entity_count=len(entities_by_id),
            max_entities=max_entities,
        )

    present_ids = {UUID(entity_id) for entity_id in entities_by_id}
    relations = [
        relation
        for relation in relations_by_id.values()
        if relation.source_entity_id in present_ids and relation.target_entity_id in present_ids
    ]
    return list(entities_by_id.values()), relations, truncated
