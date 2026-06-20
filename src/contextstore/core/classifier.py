"""Query classifier: decide a recall query's retrieval strategy (mode + depth)
before any graph work happens.

Two stages (see docs/classifier_notes.md for the full rationale):

  1. HeuristicClassifier -- pure, free, deterministic signal extraction.
     Returns a (QueryClass, confidence) pair. The majority of queries are
     classifiable here.
  2. LLMClassifier -- Haiku 4.5 via Instructor, called ONLY when the
     heuristic confidence is below CONFIDENCE_THRESHOLD. Follows the same
     Instructor pattern as extraction/extractor.py.

QueryClassifier composes the two and maps the resulting class to a
RetrievalStrategy via CLASS_TO_STRATEGY.
"""

import re

import anthropic
import instructor
import structlog
from pydantic import BaseModel, Field

from contextstore.core.config import get_settings
from contextstore.models.classification import (
    ClassifierResult,
    QueryClass,
    RetrievalStrategy,
)

logger = structlog.get_logger()

# Heuristic confidence at/above which we trust the heuristic and skip the LLM.
# Calibrated so the rules that fire on unambiguous shapes (an id/code, an
# attribute question, an explicit causal phrase) clear it, while genuinely
# ambiguous shapes (bare "how/why", keyword bags, questions with no
# recognized verb) fall below it and defer to the LLM. See
# docs/classifier_notes.md for where the cutoff came from and tuning notes.
CONFIDENCE_THRESHOLD = 0.85

# The LLM doesn't return a calibrated probability, only a class + reasoning,
# so when it decides we report a fixed confidence rather than fabricating a
# score. Chosen above neither extreme: the query was ambiguous enough to need
# the LLM, but the LLM's answer is still the system's best judgement.
_LLM_RESULT_CONFIDENCE = 0.7

# class -> retrieval knobs. exact_lookup wants fulltext (the answer is the
# named entity itself, and full-text nails identifiers vector search misses);
# single_hop and relational both want hybrid seeding, differing only in depth.
CLASS_TO_STRATEGY: dict[QueryClass, RetrievalStrategy] = {
    "exact_lookup": RetrievalStrategy(retrieval_mode="fulltext", traversal_depth=1),
    "single_hop": RetrievalStrategy(retrieval_mode="hybrid", traversal_depth=1),
    "relational": RetrievalStrategy(retrieval_mode="hybrid", traversal_depth=2),
}

_QUESTION_WORDS = {"who", "what", "where", "which", "when", "whom", "whose", "how", "why"}

# Quantitative "how X" openers are attribute questions (single_hop), NOT
# bridging questions -- they must suppress the generic "how/why" relational
# signal below. "how many cells does X produce" asks one entity's attribute.
_QUANTITATIVE_RE = re.compile(
    r"\bhow\s+(many|much|long|old|big|far|tall|heavy|often|fast|wide|deep)\b"
)

# Explicit bridging/causal language: the clearest relational signal, and the
# one case where an id/code in the query (e.g. "RG-88") should NOT pull the
# query toward exact_lookup -- a code that's merely a participant in "how is X
# connected to <code>" is relational. Substring match on the lowercased query,
# using stems so inflections are caught ("connect" -> connected/connection).
_RELATIONAL_CUES = (
    "root cause",
    "connect",  # connected to, connection between
    "related",
    "relationship",
    "relate to",
    "relates to",
    "led to",
    "caused by",
    "what caused",
    "which caused",
    "result of",
    "due to",
    "path between",
    "path from",
    "linked",
    "link between",
    "influence",  # influence(d) on/by
    "impact of",
    "stem from",
    "stems from",
    "arise from",
    "arises from",
    "trace",
    "downstream",
    "upstream",
    "depend on",
    "depends on",
)

# Attribute/relationship verbs that, paired with a who/what/where/which
# opener, mark a direct one-hop question (single_hop). Not exhaustive -- a
# question with no verb on this list falls to a lower-confidence single_hop
# guess that defers to the LLM.
_ATTRIBUTE_VERBS = (
    "lead",
    "manage",
    "manufacture",
    "make",
    "produce",
    "use",
    "work",
    "build",
    "own",
    "sponsor",
    "grant",
    "sell",
    "supply",
    "develop",
    "head",
    "run",
    "employ",
    "found",
    "create",
    "provide",
    "offer",
    "report to",
    "belong",
)
_ATTRIBUTE_VERB_RE = re.compile(
    r"\b(" + "|".join(v.replace(" ", r"\s+") for v in _ATTRIBUTE_VERBS) + r")(s|es|ed|ing)?\b"
)

# A token is "id/code-like" if it mixes letters and digits ("RG-88", "LFP-9",
# "R-2025-014", "HLX-203"). A bare number ("2025") is not a code on its own.
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'./-]*")
_HAS_LETTER_RE = re.compile(r"[A-Za-z]")
_HAS_DIGIT_RE = re.compile(r"\d")


def _is_id_code(token: str) -> bool:
    return bool(_HAS_LETTER_RE.search(token) and _HAS_DIGIT_RE.search(token))


def _is_proper_noun_phrase(tokens: list[str]) -> bool:
    """True if the query reads as a bare proper-noun phrase: most tokens
    capitalized and the first one capitalized (e.g. "Korrigan Cells Ltd",
    "Dr. Sarah Chen"). Lowercase connectors ("of", "the") are tolerated as
    long as capitalized tokens are the majority.
    """
    if not tokens:
        return False
    alpha_tokens = [t for t in tokens if _HAS_LETTER_RE.search(t)]
    if not alpha_tokens or not alpha_tokens[0][0].isupper():
        return False
    capitalized = sum(1 for t in alpha_tokens if t[0].isupper())
    return capitalized * 2 > len(alpha_tokens)


class HeuristicClassifier:
    """Stage 1: deterministic, dependency-free classification by signal
    extraction. Pure -- no I/O, fully unit-testable. `classify` returns the
    chosen class and a confidence in [0, 1]; QueryClassifier compares that
    confidence to CONFIDENCE_THRESHOLD to decide whether to call the LLM.

    Implemented as a priority cascade rather than a weighted sum: each branch
    is one named, documentable signal, and the first match wins. Ordering
    matters -- explicit relational language is checked before id/code signals
    so that a code appearing inside a bridging question doesn't hijack it.
    """

    def classify(self, query: str) -> tuple[QueryClass, float]:
        raw = query.strip()
        lower = raw.lower()
        tokens = _TOKEN_RE.findall(raw)
        n = len(tokens)
        first = tokens[0].lower() if tokens else ""
        qword = first if first in _QUESTION_WORDS else None
        quantitative = bool(_QUANTITATIVE_RE.search(lower))

        # 1. Explicit bridging/causal language -> relational. Highest priority:
        #    overrides an id/code that's only a participant in the question.
        if any(cue in lower for cue in _RELATIONAL_CUES):
            return "relational", 0.9

        # 2. Bare "how"/"why" with no causal phrase and not quantitative: a
        #    real but weaker relational lean. Deliberately below threshold so
        #    it defers to the LLM rather than committing to depth-2.
        if qword in {"how", "why"} and not quantitative:
            return "relational", 0.78

        # 3. exact_lookup: an id/code, or a bare proper-noun phrase, with no
        #    question word framing it as a question about the entity.
        if qword is None and any(_is_id_code(t) for t in tokens):
            return "exact_lookup", 0.95 if n <= 4 else 0.7
        if qword is None and _is_proper_noun_phrase(tokens) and n <= 5:
            return "exact_lookup", 0.88

        # 4. single_hop: a quantitative "how many/much/..." attribute
        #    question, or a who/what/where/which question carrying a known
        #    attribute verb.
        if quantitative:
            return "single_hop", 0.86
        if qword in {"who", "what", "where", "which"} and _ATTRIBUTE_VERB_RE.search(lower):
            return "single_hop", 0.88
        if qword in {"who", "what", "where", "which"}:
            # A question with no recognized verb: probably single_hop, but
            # uncertain enough to let the LLM confirm.
            return "single_hop", 0.6

        # 5. Nothing fired confidently (keyword bag, mixed-case noun phrase,
        #    etc.): low-confidence single_hop guess -> LLM fallback decides.
        return "single_hop", 0.3


CLASSIFIER_SYSTEM_PROMPT = """\
You classify a search query for a knowledge-graph memory system into exactly \
one of three retrieval classes. Respond only with the structured fields.

- exact_lookup: the query names a single specific entity by identifier, \
proper noun, product code, or SKU, and the answer is that entity itself or \
its own properties. Examples: "RG-88", "Recall R-2025-014", "Korrigan Cells \
Ltd", "LFP-9 Cell".
- single_hop: the query asks about a direct relationship of one clear \
subject entity, or an attribute reachable one hop away. Examples: "What does \
Vanta Battery Co manufacture?", "Who leads supply chain at Solstice \
Motors?", "How many cells does Vanta produce?".
- relational: the query asks to connect entities that do not co-occur \
directly, or asks for a cause/influence/path, requiring multiple hops. \
Examples: "What is the root cause of the Solstice recall?", "Which \
institution influenced AuroraML's architecture?", "How is Dr. Chen connected \
to RG-88?".

Pick the single best class. If a query mentions an identifier but asks how it \
connects to or is caused by something else, it is relational, not \
exact_lookup. Put a one-sentence justification in `reasoning`.\
"""


class _LLMClassification(BaseModel):
    """Instructor response_model for the LLM fallback. `reasoning` is for
    observability only (logged at DEBUG) -- it is not surfaced to callers.
    """

    query_class: QueryClass
    reasoning: str = Field(min_length=1)


class LLMClassifier:
    """Stage 2: Haiku 4.5 via Instructor, mirroring extraction/extractor.py.
    Called only on low-confidence heuristic results.
    """

    async def classify(self, query: str) -> _LLMClassification:
        settings = get_settings()
        client = instructor.from_anthropic(
            anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
        )
        result: _LLMClassification = await client.chat.completions.create(
            model=settings.classifier_model,
            max_tokens=512,
            system=CLASSIFIER_SYSTEM_PROMPT,
            response_model=_LLMClassification,
            messages=[{"role": "user", "content": query}],
        )
        return result


class QueryClassifier:
    """Two-stage classifier: heuristic first, LLM only when the heuristic is
    not confident enough. Exposes a single `classify(query) -> ClassifierResult`.
    """

    def __init__(
        self,
        heuristic: HeuristicClassifier | None = None,
        llm: LLMClassifier | None = None,
        threshold: float = CONFIDENCE_THRESHOLD,
    ) -> None:
        self._heuristic = heuristic or HeuristicClassifier()
        self._llm = llm or LLMClassifier()
        self._threshold = threshold

    async def classify(self, query: str) -> ClassifierResult:
        query_class, confidence = self._heuristic.classify(query)
        used_llm = False

        if confidence < self._threshold:
            llm_result = await self._llm.classify(query)
            logger.debug(
                "classifier.llm_fallback",
                query=query,
                heuristic_class=query_class,
                heuristic_confidence=confidence,
                llm_class=llm_result.query_class,
                reasoning=llm_result.reasoning,
            )
            query_class = llm_result.query_class
            confidence = _LLM_RESULT_CONFIDENCE
            used_llm = True

        return ClassifierResult(
            query_class=query_class,
            confidence=confidence,
            strategy=CLASS_TO_STRATEGY[query_class],
            used_llm=used_llm,
        )
