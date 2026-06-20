# ContextStore recall eval harness

A minimal way to measure `/v1/recall` against ground truth instead of judging
it by feel. This is the gate before multi-hop traversal or a query
classifier get built -- those should be justified by eval numbers, not
vibes.

## What it checks (and what it doesn't)

For each case in `dataset.yaml`, it calls `POST /v1/recall` with the case's
`query` and checks three independent things, all optional except entity
presence:
- **entity presence** -- every name in `expected_entities` appears among
  the returned entities' `name` fields
- **property values** -- `expected_properties[entity][property]` matches
  the actual value on that entity in the result
- **relation values** -- each `expected_relations` entry resolves to a real
  edge (matched by source/target/relation_type) with the expected property
  value

It still does not check ranking/ordering of results, or anything about
relation *shape* beyond the fields above. If you need that, it's a
deliberate next step, not a bug.

### History: why property/relation checks exist

Entity-presence-only checks shipped first and missed a real bug: a price
revision for Product Y extracted as a *new* `Globex-[owns]->Product Y` edge
instead of updating the existing `Globex-[relates_to]->Product Y` edge that
already held the price, because relation dedup keys on an exact
`relation_type` string match and nothing forced the same string twice for
the same fact. The old edge's price was never superseded and stayed stale
-- invisible to a check that only asks "is Globex present," since it was.
The `globex_current_price_single_hop` case's `expected_relations` entry is
what catches this class of bug now; see `eval/reports/` for the actual
red-then-green run (`*-RED-before-fix.md` / `*-GREEN-after-fix.md`) and
`core/service.py`'s `_existing_relation_types` / `extraction/extractor.py`'s
`_build_user_message` for the fix itself.

## Running it

```bash
# from the repo root, with FastAPI + FalkorDB already running
uv run python eval/run_eval.py

# point at a different backend, dataset, or tenant
uv run python eval/run_eval.py \
  --base-url http://localhost:8000 \
  --dataset eval/dataset.yaml \
  --tenant-id contextstore_demo \
  --limit 10 \
  --traversal-depth 1
```

It prints a per-category hit-rate table and a PASS/FAIL line per case to
stdout, and writes a timestamped markdown report to `eval/reports/`
(e.g. `eval/reports/20260618T144210Z.md`) so you can diff results across
runs after making a retrieval/extraction change.

**On `--limit`:** keep this at 10+ for now. The current demo tenant is tiny
(3 entities), and FalkorDB's vector index under-returns results for small
`k` on small graphs -- e.g. `k=1` returned 0 results, `k=2` returned 1, and
it took `k=6` to reliably get all 3 entities back, even though there are
only 3 total. At the default `limit=10` this is a non-issue today, but if
you add a `--limit 2`-style case later and it mysteriously fails, this is
why -- check entity count vs. limit before assuming a real regression.

## Adding cases

Open `dataset.yaml` and add an entry under `cases:`:

```yaml
- id: short_unique_id
  category: single_hop          # or: would_require_bridging, exact_term, or invent a new one
  query: "your natural-language query"
  expected_entities:
    - Entity Name One
    - Entity Name Two
  expected_properties:          # optional -- value-level check
    Entity Name One:
      some_property: "expected value"
  expected_relations:           # optional -- value-level check on an edge
    - source: Entity Name One
      target: Entity Name Two
      relation_type: relates_to
      property: some_property
      expected_value: "expected value"
  note: >
    optional -- context a human should know when this fails, e.g. the
    ground-truth value, or why this is a bridging case
```

`expected_entities` matches by entity **name**, not id -- ids are
regenerated every time a tenant is wiped/reseeded, names are stable enough
for this purpose at this scale. Same for `source`/`target` in
`expected_relations`.

**Property and relation values aren't fully deterministic across
re-ingestions of the same sentence** -- the LLM can name an extracted
property `price` one run and `quoted_price` another, even for an otherwise
identical write. If a case starts failing only on a property/relation NAME
(not the underlying value), check `GET /v1/graph` before assuming a
regression; you may just need to update the case to match the LLM's latest
naming choice. This isn't unique to property names either -- the bug this
extension was built to catch (see History below) is the same
non-determinism landing on `relation_type` instead.

To find real ground truth for a new case (don't guess at what's in the
graph):

```bash
curl -s "http://localhost:8000/v1/graph?tenant_id=contextstore_demo" | python3 -m json.tool
```

Read the actual entities/relations/claims it returns, then write a case
that's true of that data.

## Building up a bigger graph to get a real feel for it

Right now the demo tenant only has 3 entities -- not enough to tell whether
multi-hop traversal actually matters in practice (see the
`acme_price_bridging` case's note in `dataset.yaml` for why). To grow it:

1. Write a handful of sentences the way the existing demo scenario does --
   short, factual, naming entities that should connect to existing ones
   (reuse "Acme Corp", "Globex", "Product Y", or introduce new
   customers/suppliers/products that connect to them).
2. Ingest each one:

   ```bash
   curl -s -X POST http://localhost:8000/v1/memories -H "Content-Type: application/json" -d '{
     "content": "Acme Corp also ordered 200 units of Product Z from Initech.",
     "scope": {"tenant_id": "contextstore_demo"},
     "source": "crm-agent"
   }'
   ```

   Or loop over a list of sentences in Python with `httpx` (already a
   dependency) if you want to ingest many at once:

   ```python
   import httpx

   sentences = [
       ("Acme Corp also ordered 200 units of Product Z from Initech.", "crm-agent"),
       ("Initech quoted $9.10 per unit for Product Z.", "supplier-conversation-agent"),
       # ...
   ]
   with httpx.Client(base_url="http://localhost:8000") as client:
       for content, source in sentences:
           r = client.post("/v1/memories", json={
               "content": content,
               "scope": {"tenant_id": "contextstore_demo"},
               "source": source,
           })
           r.raise_for_status()
           print(content, "->", [e["name"] for e in r.json()["entities"]])
   ```

3. Check what actually landed with `GET /v1/graph?tenant_id=contextstore_demo`
   (entity resolution might merge things differently than you expect --
   don't assume, look).
4. Add `dataset.yaml` cases against the real result, including ones that
   force a longer bridge (e.g. an entity 3+ hops from another) once the
   graph is big enough that vector search at `limit=10` can no longer
   trivially return the whole graph for every query -- that's the point at
   which this harness can actually start telling you whether multi-hop is
   needed, rather than masking the question the way it does today.
5. Re-run `uv run python eval/run_eval.py` and compare the new report in
   `eval/reports/` against the previous one.

## Using this with Claude (chat, not Code) for a manual eval pass

If you want a second pass of judgment on top of the numbers -- e.g. "does
this query's returned entity set actually make sense for what was asked" --
paste this into a Claude chat:

1. Paste the contents of `eval/dataset.yaml`.
2. Paste the latest report from `eval/reports/`.
3. Paste the raw output of `curl -s "http://localhost:8000/v1/graph?tenant_id=contextstore_demo"`.
4. Ask: "Given this ground-truth dataset, this eval report, and this raw
   graph state, which FAIL cases look like genuine retrieval gaps vs. which
   look like the ground truth itself being wrong or underspecified? Are
   there missing cases that this graph's data could support?"

That gives Claude the same three things this harness's author needed to
write `dataset.yaml` honestly: the cases, the measured outcome, and the
actual data they're ground-truthed against.
