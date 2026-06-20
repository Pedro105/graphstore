"""Unit tests for RecallSynthesiser and subgraph serialisation, fully mocked
(no real LLM calls).

Covers: a successful synthesis (answer populated, grounded ids filtered to the
real subgraph), the empty-subgraph short-circuit (insufficient_data, no LLM
call), the compact serialisation (entity/relation/conflict rendering), and
graceful degradation when synthesis raises inside recall().
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from contextstore.core.service import recall
from contextstore.core.synthesiser import RecallSynthesiser, serialise_subgraph
from contextstore.graph.store import GraphStore
from contextstore.models.claim import apply_claim
from contextstore.models.entity import Entity
from contextstore.models.provenance import Provenance
from contextstore.models.recall import RecallResult, RetrievalStats
from contextstore.models.relation import Relation
from contextstore.models.scope import Scope
from contextstore.models.synthesis import SynthesisResult
from contextstore.vector.embeddings import EmbeddingProvider

SCOPE = Scope.from_dict({"tenant_id": "acme", "user_id": "u_1"})
PROVENANCE = Provenance(source="agent_1")
# Stats are irrelevant to synthesis; a placeholder satisfies the required field.
STATS = RetrievalStats(
    total_ms=1.0,
    retrieval_ms=1.0,
    synthesis_ms=None,
    seeds_found=0,
    nodes_traversed=0,
    relations_found=0,
    depth_reached=1,
    query_class="manual",
    used_llm_classifier=False,
)


def make_entity(**overrides) -> Entity:
    defaults = dict(scope=SCOPE, provenance=PROVENANCE)
    defaults.update(overrides)
    return Entity(**defaults)


def make_client(synthesis: SynthesisResult) -> AsyncMock:
    """An Instructor-shaped async client whose create() returns `synthesis`."""
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(return_value=synthesis)
    return client


async def test_synthesise_populates_answer_and_filters_grounded_ids():
    real = make_entity(name="Korrigan Cells Ltd", entity_type="Organization")
    other = make_entity(name="LFP-9 Cell", entity_type="Product")
    result = RecallResult(query="who is Korrigan?", scope=SCOPE, entities=[real, other], stats=STATS)

    # Model cites one real id and one id that isn't in the subgraph.
    returned = SynthesisResult(
        answer="Korrigan Cells Ltd is a tier-2 supplier.",
        grounded_entity_ids=[str(real.id), "00000000-0000-0000-0000-000000000000"],
        confidence="high",
        caveat=None,
    )
    client = make_client(returned)
    synthesiser = RecallSynthesiser(client=client)

    out = await synthesiser.synthesise("who is Korrigan?", result, SCOPE)

    client.chat.completions.create.assert_awaited_once()
    assert out.answer == "Korrigan Cells Ltd is a tier-2 supplier."
    # Bogus id dropped; only the real subgraph id survives.
    assert out.grounded_entity_ids == [str(real.id)]
    assert out.confidence == "high"


async def test_synthesise_short_circuits_on_empty_subgraph():
    result = RecallResult(query="anything?", scope=SCOPE, entities=[], stats=STATS)
    client = make_client(
        SynthesisResult(answer="should not be used", grounded_entity_ids=[], confidence="high")
    )
    synthesiser = RecallSynthesiser(client=client)

    out = await synthesiser.synthesise("anything?", result, SCOPE)

    # No entities -> no LLM call, deterministic insufficient_data.
    client.chat.completions.create.assert_not_awaited()
    assert out.confidence == "insufficient_data"
    assert out.grounded_entity_ids == []
    assert out.caveat


def test_serialise_subgraph_renders_entities_relations_and_conflict():
    # Build a claim history with a superseded value to exercise conflict notes.
    early = Provenance(source="agent_a", created_at=datetime(2025, 1, 1, tzinfo=UTC))
    late = Provenance(source="agent_b", created_at=datetime(2025, 6, 1, tzinfo=UTC))
    claims = apply_claim([], early, {"tier": "tier-3"})
    claims = apply_claim(claims, late, {"tier": "tier-2"})

    korrigan = make_entity(
        name="Korrigan Cells Ltd",
        entity_type="Organization",
        properties={"tier": "tier-2"},
        claims=claims,
        contributing_sources=["agent_a", "agent_b"],
    )
    product = make_entity(name="LFP-9 Cell", entity_type="Product")
    relation = Relation(
        source_entity_id=korrigan.id,
        target_entity_id=product.id,
        relation_type="produces",
        scope=SCOPE,
        provenance=PROVENANCE,
    )
    result = RecallResult(
        query="What does Korrigan produce?",
        scope=SCOPE,
        entities=[korrigan, product],
        relations=[relation],
        stats=STATS,
    )

    text = serialise_subgraph(result)

    assert "QUERY: What does Korrigan produce?" in text
    assert "Korrigan Cells Ltd [Organization]" in text
    assert "LFP-9 Cell [Product]" in text
    assert str(korrigan.id) in text  # id present so the model can cite it
    assert "Korrigan Cells Ltd -[produces]-> LFP-9 Cell" in text
    # Active value shown, superseded value flagged as a conflict (not as current).
    assert "tier='tier-2'" in text
    assert "conflict on tier" in text
    assert "tier-3" in text


async def test_recall_degrades_gracefully_when_synthesis_raises():
    seed = make_entity(name="Acme Corp", entity_type="Organization")
    graph_store = AsyncMock(spec=GraphStore)
    graph_store.find_similar_entities.return_value = [(seed, 0.95)]
    graph_store.find_by_fulltext.return_value = []
    graph_store.traverse_from_seeds.return_value = ([seed], [], False)
    embedding_provider = AsyncMock(spec=EmbeddingProvider)
    embedding_provider.embed.return_value = [1.0, 0.0, 0.0, 0.0]

    failing = AsyncMock(spec=RecallSynthesiser)
    failing.synthesise.side_effect = RuntimeError("haiku unavailable")

    result = await recall(
        query="Acme Corp",
        scope=SCOPE,
        graph_store=graph_store,
        embedding_provider=embedding_provider,
        retrieval_mode="vector",
        synthesise=True,
        synthesiser=failing,
    )

    # Synthesis failure must not propagate; structured result returned cleanly.
    failing.synthesise.assert_awaited_once()
    assert result.synthesis is None
    assert {entity.id for entity in result.entities} == {seed.id}
