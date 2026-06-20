# Query classifier — implementation notes

Developer post-mortem for the two-stage recall query classifier
(`core/classifier.py`, wired into `core/service.py`'s `recall()`). Not an
end-user doc. Written right after the implementation landed; reflects what
the eval and manual probing actually showed, including where the thing is
weak.

## What it does and why it's shaped this way

`recall()` used to take a fixed `retrieval_mode` (`hybrid`) and
`traversal_depth` (`1`) on every call. The classifier replaces that with a
per-query routing decision: classify the query into one of three shapes and
map the shape to a `RetrievalStrategy`:

| class          | retrieval_mode | traversal_depth | intuition                                            |
|----------------|----------------|-----------------|------------------------------------------------------|
| `exact_lookup` | `fulltext`     | 1               | answer is the named entity's own properties          |
| `single_hop`   | `hybrid`       | 1               | answer is a direct relationship / one-hop attribute  |
| `relational`   | `hybrid`       | 2               | must connect entities that don't co-occur directly   |

The whole point is to *not* run depth-2 traversal on every query (cost and
noise) while still reaching the bridge entities that depth-2 queries need.
`exact_lookup` additionally drops to pure `fulltext` because the failure mode
that motivated hybrid search in the first place — alphanumeric codes like
`RG-88` that vector search ranks poorly — is exactly the `exact_lookup` case,
and the vector half mostly adds noise there.

Two design decisions that aren't obvious from the spec:

- **`ClassifierResult` / `RetrievalStrategy` are pydantic models, not the
  `@dataclass`es the brief sketched.** They cross the core→api boundary
  (they ride on `RecallResult`, which is a FastAPI `response_model`), so they
  have to serialize cleanly and live in `models/`. They're in
  `models/classification.py`, which also became the new home of
  `RetrievalMode` — `recall.py` re-exports it. That move exists purely to
  break a circular import: `RecallResult` needs `ClassifierResult`, and
  `RetrievalStrategy` needs `RetrievalMode`; if `RetrievalMode` had stayed in
  `recall.py` the two modules would import each other.

- **Caller-supplied routing always wins, and "supplied" means "not `None`."**
  `RecallRequest.retrieval_mode` and `.traversal_depth` became
  `Optional[...] = None`. If the caller pins *either*, the classifier is
  skipped entirely and the other knob falls back to its old static default
  (`hybrid` / `1`). This is what keeps the eval harness — which always sends
  an explicit `traversal_depth` — behaving exactly as before (see eval
  section). The classifier only runs when both knobs are left unset.

## Stage 1: the heuristic classifier

`HeuristicClassifier.classify(query) -> (QueryClass, confidence)`. Pure, no
I/O, fully unit-tested. It is a **priority cascade**, not a weighted sum:
each branch is one named signal, the first match wins, and the order is the
important part. Confidence is a fixed number attached to each branch, hand-
calibrated so that branches firing on unambiguous shapes clear the 0.85
threshold and ambiguous ones fall below it.

Order and signals (top = highest priority):

1. **Explicit bridging/causal language → `relational`, 0.90.** Substring match
   against `_RELATIONAL_CUES` (stems: `root cause`, `connect`, `related`,
   `led to`, `caused by`, `path between`, `influence`, `linked`, `depend on`,
   `trace`, …). This is checked *first and deliberately* so that an id/code
   appearing inside a bridging question ("How is **RG-88** connected to Dr.
   Chen?") is routed relational, not hijacked by the exact-lookup id signal
   below.
2. **Bare `how`/`why` with no causal phrase and not quantitative →
   `relational`, 0.78.** A real but weak signal. Set *below* threshold on
   purpose: "how does X work" is genuinely ambiguous between single-hop and
   relational, so it defers to the LLM rather than committing to depth-2.
3. **Quantitative `how many|much|long|…` → suppresses signal 2.** Detected
   before it can be read as relational `how`; lands in signal 6 as a
   single-hop attribute question. This is the "a 'how' query that is actually
   single-hop" case.
4. **id/code token, no question word → `exact_lookup`, 0.95 (≤4 tokens) /
   0.70 (longer).** "id/code" = a token mixing letters and digits (`RG-88`,
   `LFP-9`, `R-2025-014`). A bare year (`2025`) is not a code. The length
   cut-off encodes "a code on its own is a lookup; a code buried in a longer
   phrase is probably part of a larger question" → the longer form drops
   below threshold and asks the LLM.
5. **Bare proper-noun phrase, no question word, ≤5 tokens → `exact_lookup`,
   0.88.** "Proper-noun phrase" = majority of alphabetic tokens capitalized
   and the first one capitalized ("Korrigan Cells Ltd", "Dr. Sarah Chen").
6. **`who/what/where/which` + a known attribute verb → `single_hop`, 0.88;
   quantitative `how` → 0.86; `who/what/where/which` with no recognized verb
   → 0.60.** The attribute-verb list (`manufacture`, `lead`, `sponsor`,
   `produce`, `use`, …) is a closed set; a question with a verb outside it
   gets the 0.60 "probably single-hop, ask the LLM" treatment.
7. **Fallthrough → `single_hop`, 0.30.** Keyword bags, mixed-case noun
   phrases, anything that matched nothing. Always defers to the LLM.

### Where the 0.85 threshold came from

It's a calibration, not a measurement — there is no labelled query set to
fit against (the eval dataset has 11 queries). The number was chosen so the
branch confidences split cleanly:

- Above 0.85 (trust heuristic): the unambiguous shapes — id/code (0.95),
  proper noun (0.88), attribute question (0.88/0.86), explicit causal phrase
  (0.90).
- Below 0.85 (ask the LLM): the genuinely uncertain shapes — bare how/why
  (0.78), long id phrase (0.70), verbless question (0.60), fallthrough
  (0.30).

The gap between the two clusters (0.78 vs 0.86) is wide, so the exact cutoff
is not sensitive anywhere in [0.80, 0.85]. **It should be revisited the
moment there's a real labelled query log**, at which point these hand
numbers should be replaced by measured precision per branch. Until then,
treat the confidences as ordinal (which branch fired) more than cardinal.

## Stage 2: the LLM fallback

`LLMClassifier` — Haiku 4.5 via Instructor, same pattern as
`extraction/extractor.py` (`instructor.from_anthropic(...)`,
`response_model=...`). Called only when stage 1 returns confidence < 0.85.
Model id comes from the new `settings.classifier_model` (defaults to the same
Haiku as extraction, but separable so the two LLM uses can be pointed/costed
independently).

Response model is `_LLMClassification { query_class, reasoning }`. The
`reasoning` field is observability only — logged at DEBUG in
`QueryClassifier.classify` (`classifier.llm_fallback` event) and never
surfaced to the caller. It exists so that when a routing decision looks
wrong in a log, you can see *why* the model chose it without re-running.

The exact system prompt is `CLASSIFIER_SYSTEM_PROMPT` in `core/classifier.py`:
the three class definitions (one line each), 2–4 worked examples per class,
and one explicit disambiguation rule — *"if a query mentions an identifier
but asks how it connects to or is caused by something else, it is relational,
not exact_lookup."* That rule is in the prompt because it's the single
hardest call and the one the heuristic also has to special-case (signal 1
beating signal 4). The few-shot examples were chosen to mirror the eval graph
domains (battery recalls, ML labs, biotech) so the model sees the actual
shape of queries this store gets, and to include the adversarial id-in-
relational case (`"How is Dr. Chen connected to RG-88?"`) rather than only
clean ones.

When the LLM decides, `ClassifierResult.confidence` is reported as a fixed
`_LLM_RESULT_CONFIDENCE = 0.70`, not a heuristic score and not a fabricated
model probability — the model doesn't emit a calibrated one. `used_llm=True`
is the field that actually matters for cost tracking; the 0.70 is just an
honest "this was the ambiguous bucket" marker.

## Where the heuristics fail

**Falls through to the LLM (low confidence, correct to defer):**

- Keyword-bag queries with no question word, verb, code, or proper-noun
  shape — exactly the `isolation` eval queries ("biotech startup pancreatic
  cancer drug compound research pipeline"). Confidence 0.30.
- Mixed-case noun phrases like "Series A funding round" (capitalized tokens
  not a majority → not a proper-noun phrase, no code, no verb). Confidence
  0.30.
- "how/why X work" with no causal phrase; verbless `what/which` questions
  ("What is HLX-203?"). These *should* go to the LLM — they're real
  ambiguities, not heuristic gaps.

**Misclassified with high confidence — the dangerous case:** a query whose
*surface form* gives no hint of the depth it actually needs. The clearest
example is in our own eval set: the bridging cases are bare proper nouns
("Dr. Sarah Chen", "Dr. Amara Osei", "Korrigan Cells Ltd") that the heuristic
calls `exact_lookup` at 0.88 and routes to depth 1 — but they're tuned to
depth 2 because the *intended answer* is two hops away. Nothing in the string
"Dr. Sarah Chen" says "I want the compound her study was reversed by." The
LLM can't recover this either; it's not an ambiguity in the query, it's
information that simply isn't in the query. See the next section.

Other known false-positive risks (not in the eval set, found by inspection):

- Substring stems can misfire: `connect` matches "connector", `trace` matches
  "traceability", `influence` matches "influencer". A single-hop question
  about "the connector cable" would be mis-routed relational at 0.90. Cheap
  to fix with word-boundary matching if it ever shows up; left as substring
  for now because the stems catch inflections (connected/connection/connects)
  that a strict word list would miss.
- The attribute-verb list is closed, so "Who *founded* Helios?" works but
  "Who *chairs* Helios?" falls to the 0.60 verbless bucket and burns an LLM
  call. Expanding the list is the obvious lever if LLM-call rate is too high.

## What the eval run revealed

Eval harness, `tenant_id: eval_test`, before and after wiring: **14/14 both
times, no category regressed.** That's the expected non-result: the harness
sends an explicit `traversal_depth` on every request, so the
caller-wins rule skips the classifier and the recall path is byte-for-byte
what it was. The eval confirms the wiring is inert when routing is pinned —
which is the contract — but it does **not** exercise the classifier. (Reports:
`eval/reports/20260618T214301Z.md` and the `…211756Z` baseline.)

To actually test the routing decision I ran the heuristic standalone over the
eval queries and compared its chosen depth to each case's manually-tuned
depth:

| query                                              | category   | heuristic class | conf | depth | tuned | agree |
|----------------------------------------------------|------------|-----------------|------|-------|-------|-------|
| Korrigan Cells Ltd                                 | exact_term | exact_lookup    | 0.88 | 1     | 1     | ✅    |
| RG-88                                              | exact_term | exact_lookup    | 0.95 | 1     | 1     | ✅    |
| What component does Korrigan Cells Ltd produce?    | single_hop | single_hop      | 0.88 | 1     | 1     | ✅    |
| What open source project does NeoSilicon sponsor?  | single_hop | single_hop      | 0.88 | 1     | 1     | ✅    |
| What designation did the FDA grant?                | single_hop | single_hop      | 0.88 | 1     | 1     | ✅    |
| Dr. Sarah Chen                                     | bridging   | exact_lookup    | 0.88 | 1     | 2     | ❌    |
| Dr. Amara Osei                                     | bridging   | exact_lookup    | 0.88 | 1     | 2     | ❌    |
| Korrigan Cells Ltd                                 | bridging   | exact_lookup    | 0.88 | 1     | 2     | ❌    |
| Series A funding round                             | provenance | (→ LLM) 0.30    | —    | 1*    | 1     | ✅*   |
| biotech startup … research pipeline                | isolation  | (→ LLM) 0.30    | —    | 1*    | 1     | ✅*   |
| electric vehicle battery … component defect        | isolation  | (→ LLM) 0.30    | —    | 1*    | 1     | ✅*   |

`*` = heuristic falls below threshold; in production the LLM decides. The
depth shown is the heuristic's pre-LLM fallthrough guess (single_hop → 1),
which happens to match the tuned depth, but production would spend an LLM
call on these three.

**Heuristic depth agreement: 8/11.** All three disagreements are bridging
cases, and they're the *same* failure described above: bare-proper-noun
queries the heuristic confidently routes shallow. The most damning data point
is that **"Korrigan Cells Ltd" appears twice with two different tuned depths**
— depth 1 as an `exact_term` lookup, depth 2 as a `bridging` query — for the
*identical query string*. No classifier that sees only the query text can be
right about both. The depth a bridging query needs is a property of the
answer the caller wants, not of the query, and our routing model has no
channel for that intent.

This is signal, not a bug to paper over. Two honest readings:

1. The bridging eval cases are arguably under-specified queries — a real user
   wanting the 2-hop answer would more likely ask "what is Dr. Chen connected
   to" (which *does* trip the relational signal) than just type her name.
2. If we want to serve bare-entity queries that still need depth, routing
   from the query string alone is the wrong layer. Options below.

## Recommended future improvements

- **Carry caller intent.** A lightweight `depth_hint` or "explain how X
  relates to Y" affordance in `RecallRequest` would resolve the bridging
  ambiguity that no text classifier can. This is the highest-value change.
- **Adaptive depth instead of fixed-by-class.** Seed at depth 1, and if the
  result is thin (few entities / low-degree seeds), expand to depth 2 and
  re-traverse. This sidesteps classification for the exact case it's worst at
  (bare entity that happens to need a hop) and is robust to Anomaly 3's
  small-graph under-seeding.
- **Replace hand-set confidences with measured ones.** Once there's a query
  log, label a few hundred queries and set per-branch confidence from
  observed precision; re-derive the threshold from the precision/recall curve
  rather than eyeballing the 0.78/0.86 gap.
- **Word-boundary relational cues** to kill the `connector`/`influencer`
  substring false positives, and **expand the attribute-verb list** to cut
  the LLM-fallback rate on ordinary single-hop questions.
- **Cache classification by normalized query** — it's deterministic for the
  heuristic path and stable enough for the LLM path that a small LRU would
  remove most repeat LLM calls in agent workloads that re-issue queries.
