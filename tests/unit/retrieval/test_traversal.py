"""Unit tests for the pure BFS traversal helper (retrieval/traversal.py).

No FalkorDB: the graph is an in-memory adjacency map, and the seed/neighbour
fetchers close over it -- this is the "mocked graph store" for traverse_from_
seeds' BFS logic. Covers depth bounding, cycle handling, the max_entities
cap, and natural termination.
"""

from uuid import UUID, uuid4

from contextstore.models.entity import Entity
from contextstore.models.provenance import Provenance
from contextstore.models.relation import Relation
from contextstore.models.scope import Scope
from contextstore.retrieval.traversal import breadth_first_traverse

SCOPE = Scope.from_dict({"tenant_id": "acme"})
PROVENANCE = Provenance(source="test")


class FakeGraph:
    """In-memory directed graph; traversal treats edges as undirected (a
    neighbour reached from either endpoint counts), matching the real store."""

    def __init__(self) -> None:
        self.entities: dict[str, Entity] = {}
        # adjacency[a] = list of (b, relation) for stored edge a -> b
        self.out_edges: dict[str, list[tuple[str, Relation]]] = {}

    def add_entity(self, name: str) -> str:
        entity = Entity(name=name, entity_type="thing", scope=SCOPE, provenance=PROVENANCE)
        eid = str(entity.id)
        self.entities[eid] = entity
        self.out_edges.setdefault(eid, [])
        return eid

    def add_edge(self, source_id: str, target_id: str) -> None:
        relation = Relation(
            source_entity_id=UUID(source_id),
            target_entity_id=UUID(target_id),
            relation_type="rel",
            scope=SCOPE,
            provenance=PROVENANCE,
        )
        self.out_edges[source_id].append((target_id, relation))

    async def fetch_seeds(self, ids: list[str]) -> list[Entity]:
        return [self.entities[i] for i in ids if i in self.entities]

    async def fetch_neighbours(self, frontier_ids: list[str]) -> list[tuple[Entity, Relation]]:
        frontier = set(frontier_ids)
        pairs: list[tuple[Entity, Relation]] = []
        for src, edges in self.out_edges.items():
            for dst, relation in edges:
                # Undirected: an edge connects the two endpoints either way.
                # All edges incident to the frontier are returned (including to
                # already-visited neighbours), matching the real store -- the
                # BFS dedups and decides re-expansion.
                if src in frontier:
                    pairs.append((self.entities[dst], relation))
                elif dst in frontier:
                    pairs.append((self.entities[src], relation))
        return pairs

    async def traverse(self, seed_ids: list[str], depth: int, max_entities: int = 200):
        return await breadth_first_traverse(
            seed_ids,
            depth,
            max_entities,
            self.fetch_seeds,
            self.fetch_neighbours,
            tenant_id="acme",
        )


def _names(entities: list[Entity]) -> set[str]:
    return {entity.name for entity in entities}


async def test_linear_chain_depth_bounds_reachability():
    g = FakeGraph()
    a, b, c, d = (g.add_entity(n) for n in "ABCD")
    g.add_edge(a, b)
    g.add_edge(b, c)
    g.add_edge(c, d)

    entities, _, truncated = await g.traverse([a], depth=1)
    assert _names(entities) == {"A", "B"}
    assert truncated is False

    entities, _, _ = await g.traverse([a], depth=2)
    assert _names(entities) == {"A", "B", "C"}

    entities, _, _ = await g.traverse([a], depth=3)
    assert _names(entities) == {"A", "B", "C", "D"}


async def test_relations_only_between_accumulated_entities():
    g = FakeGraph()
    a, b, c = (g.add_entity(n) for n in "ABC")
    g.add_edge(a, b)
    g.add_edge(b, c)

    # depth=1 reaches {A, B}; the B->C relation must be excluded since C is
    # not in the accumulated entity set.
    entities, relations, _ = await g.traverse([a], depth=1)
    assert _names(entities) == {"A", "B"}
    assert len(relations) == 1
    rel = relations[0]
    assert {rel.source_entity_id, rel.target_entity_id} == {UUID(a), UUID(b)}


async def test_edges_between_seeds_are_returned():
    # Regression: when interconnected entities are all seeds, the edges
    # connecting them must still be returned. Previously the visited-exclusion
    # in the neighbour fetch dropped every seed<->seed edge, so a recall whose
    # seeds were interconnected came back with entities but 0 relations.
    g = FakeGraph()
    a, b, c = (g.add_entity(n) for n in "ABC")
    g.add_edge(a, b)
    g.add_edge(b, c)
    g.add_edge(a, c)

    entities, relations, _ = await g.traverse([a, b, c], depth=1)

    assert _names(entities) == {"A", "B", "C"}
    assert len(relations) == 3
    endpoints = {
        frozenset({relation.source_entity_id, relation.target_entity_id}) for relation in relations
    }
    assert endpoints == {
        frozenset({UUID(a), UUID(b)}),
        frozenset({UUID(b), UUID(c)}),
        frozenset({UUID(a), UUID(c)}),
    }


async def test_cycle_terminates_and_visits_each_node_once():
    g = FakeGraph()
    a, b, c = (g.add_entity(n) for n in "ABC")
    g.add_edge(a, b)
    g.add_edge(b, c)
    g.add_edge(c, a)  # cycle

    entities, _, truncated = await g.traverse([a], depth=3)

    assert _names(entities) == {"A", "B", "C"}
    # Each entity present exactly once (no infinite loop / re-add).
    assert len(entities) == 3
    assert truncated is False


async def test_max_entities_cap_truncates_high_fan_out():
    g = FakeGraph()
    hub = g.add_entity("hub")
    for i in range(100):
        leaf = g.add_entity(f"leaf{i}")
        g.add_edge(hub, leaf)

    entities, _, truncated = await g.traverse([hub], depth=1, max_entities=10)

    assert truncated is True
    assert len(entities) <= 10


async def test_natural_termination_when_depth_exceeds_graph():
    g = FakeGraph()
    a, b, c = (g.add_entity(n) for n in "ABC")
    g.add_edge(a, b)
    g.add_edge(a, c)
    # Everything reachable at depth 1; ask for depth 5.

    entities, _, truncated = await g.traverse([a], depth=5)

    assert _names(entities) == {"A", "B", "C"}
    assert truncated is False


async def test_seeds_with_no_edges_returned_alone():
    g = FakeGraph()
    a = g.add_entity("A")

    entities, relations, truncated = await g.traverse([a], depth=3)

    assert _names(entities) == {"A"}
    assert relations == []
    assert truncated is False


async def test_multiple_seeds_merged_subgraph():
    g = FakeGraph()
    a, b, x, y = (g.add_entity(n) for n in ("A", "B", "X", "Y"))
    g.add_edge(a, x)
    g.add_edge(b, y)

    entities, _, _ = await g.traverse([a, b], depth=1)

    assert _names(entities) == {"A", "B", "X", "Y"}


async def test_unreachable_seed_id_is_skipped():
    g = FakeGraph()
    a = g.add_entity("A")
    g.add_edge(a, g.add_entity("B"))
    missing = str(uuid4())

    entities, _, _ = await g.traverse([a, missing], depth=1)

    assert _names(entities) == {"A", "B"}
