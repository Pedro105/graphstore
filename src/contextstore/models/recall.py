"""RecallResult: structured output of a recall() query.

Structured data for now, not prose -- synthesizing a natural-language
answer from this is a later step.
"""

from pydantic import BaseModel, Field

from contextstore.models.classification import ClassifierResult, RetrievalMode
from contextstore.models.entity import Entity
from contextstore.models.relation import Relation
from contextstore.models.scope import Scope
from contextstore.models.synthesis import SynthesisResult

# Re-exported from models/classification.py (its true home -- see that
# module for why) so existing `from contextstore.models.recall import
# RetrievalMode` import sites keep working.
__all__ = ["RecallResult", "RetrievalMode", "RetrievalStats"]


class RetrievalStats(BaseModel):
    """Per-recall timing and graph metrics, captured with time.perf_counter()
    inside recall() (see core/service.py). Always present on a RecallResult so
    callers/UI can show how a query was answered without a tracing backend."""

    total_ms: float  # end-to-end recall latency in milliseconds
    retrieval_ms: float  # start to traversal complete (excludes synthesis)
    synthesis_ms: float | None  # synthesis latency, None when synthesis didn't run
    seeds_found: int  # entities returned by hybrid fusion before traversal
    nodes_traversed: int  # total entities in the final subgraph
    relations_found: int  # total relations in the final subgraph
    depth_reached: int  # actual traversal depth used (classifier- or caller-chosen)
    query_class: str  # classifier class, or "manual" when routing was pinned
    used_llm_classifier: bool  # whether the Haiku classifier fallback fired


class RecallResult(BaseModel):
    query: str = Field(min_length=1)
    scope: Scope
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    # Populated only when recall() ran the classifier (i.e. the caller left
    # both retrieval_mode and traversal_depth unspecified). None when the
    # caller pinned routing explicitly, since no classification happened.
    classifier_result: ClassifierResult | None = None
    # True when multi-hop traversal hit the max_entities cap and the returned
    # subgraph was truncated before the full depth/graph was exhausted.
    truncated: bool = False
    # Optional natural-language answer synthesised from the entities/relations
    # above. Populated only when recall() was called with synthesise=True and
    # the synthesis step succeeded; None otherwise (including when synthesis
    # was requested but the LLM call failed -- failures degrade to structured
    # output, they don't propagate). The structured entities/relations are
    # always returned regardless: synthesis is additive, never a replacement.
    synthesis: SynthesisResult | None = None
    # Timing + graph metrics for this recall. Required (never None): the recall
    # pipeline always populates it (see core/service.py).
    stats: RetrievalStats
