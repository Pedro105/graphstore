"""Query-classification models: how a recall query is routed before any
graph work happens.

`RetrievalMode` lives here (rather than in recall.py) so that both the
retrieval-mode enum and the classifier types form a single dependency-free
leaf module: recall.py imports from here and re-exports `RetrievalMode` for
back-compat, which keeps this module from having to import recall.py back
(that would be circular, since RecallResult carries a ClassifierResult).
"""

from typing import Literal

from pydantic import BaseModel, Field

# How recall() seeds entities before traversal: pure vector similarity,
# pure full-text keyword search, or both fused via reciprocal rank fusion
# (retrieval/fusion.py). See core/service.py's recall().
RetrievalMode = Literal["vector", "fulltext", "hybrid"]

# The three query shapes the classifier routes between. See core/classifier.py
# and docs/classifier_notes.md for the signals behind each.
#   exact_lookup -- asking for a specific named entity by id/proper noun/code;
#                   the answer is the entity's own properties (depth 1).
#   single_hop   -- asking about a direct relationship or a one-hop-away
#                   attribute (depth 1).
#   relational   -- asking to connect entities that don't co-occur directly,
#                   requiring a multi-hop traversal (depth 2).
QueryClass = Literal["exact_lookup", "single_hop", "relational"]


class RetrievalStrategy(BaseModel):
    """The retrieval knobs a query class maps to. Consumed by recall() to set
    `retrieval_mode` and `traversal_depth` when the caller didn't pin them.
    """

    retrieval_mode: RetrievalMode
    traversal_depth: int = Field(ge=1)


class ClassifierResult(BaseModel):
    """Outcome of classifying one query, surfaced on RecallResult so callers
    (and the frontend recall panel) can see how their query was routed.

    `confidence` is the heuristic confidence when `used_llm` is False; when
    the heuristic fell below threshold and the LLM decided, it's a fixed
    constant (see core/classifier.py's `_LLM_RESULT_CONFIDENCE`) rather than
    a heuristic score, since the LLM doesn't emit a calibrated probability.
    `used_llm` is for cost/observability accounting.
    """

    query_class: QueryClass
    confidence: float = Field(ge=0.0, le=1.0)
    strategy: RetrievalStrategy
    used_llm: bool
