"""SynthesisResult: the optional natural-language answer produced from a
RecallResult.

Synthesis is additive -- it never replaces the structured entities/relations
on a RecallResult, it sits alongside them (see RecallResult.synthesis). The
prose answer is grounded strictly in the retrieved subgraph: `answer` states
only facts present in the entities/relations passed to the synthesiser, and
`grounded_entity_ids` records which of those entities the answer actually drew
on (validated against the real subgraph, so it can't cite an entity that
wasn't retrieved).
"""

from typing import Literal

from pydantic import BaseModel, Field

# high/medium/low describe how well the retrieved subgraph supports the answer;
# insufficient_data means the subgraph did not contain enough to answer at all
# (the synthesiser must use this rather than inventing an answer).
SynthesisConfidence = Literal["high", "medium", "low", "insufficient_data"]


class SynthesisResult(BaseModel):
    answer: str = Field(min_length=1)
    # Entity ids (as strings) the answer draws on. Populated by the model and
    # then filtered down to ids that actually exist in the retrieved subgraph.
    grounded_entity_ids: list[str] = Field(default_factory=list)
    confidence: SynthesisConfidence
    # Populated when confidence is medium/low/insufficient_data, or when the
    # answer is partial (e.g. one hop of a two-hop chain is present but the
    # connecting fact is missing) or rests on conflicting source claims.
    caveat: str | None = None
