"""Populate tenant `eval_test` with a 3-cluster graph for the eval harness.

Run against a live backend:

    uv run python scripts/populate_graph.py
    uv run python scripts/populate_graph.py --base-url http://localhost:8000

Each FACTS tuple is (content, source) and becomes one POST /v1/memories
call -- one extraction call per tuple, never batched, so the only relations
that can form are the ones the LLM sees within a single tuple's content.

ENGINEERED 2-HOP CHAINS (the eval's bridging cases are built against these).
Exact relation_type strings are illustrative, not literal -- the extractor
names them per-call (see extraction/prompts.py) and the exact verb varies
across ingestion runs; traverse() is undirected, so the chain holds
regardless of edge direction:
  Cluster A: Dr. Sarah Chen -[authored]-> CRISPR-X stability study
             -[cited_by RiboGen]-> RG-88
  Cluster B: Dr. Amara Osei -[authored]-> Cascade v3 architecture
             whitepaper <-[influenced_by]- AuroraML
  Cluster C: Korrigan Cells Ltd -[produces]-> LFP-9 Cell
             -[identified_as_root_cause_of]-> Voluntary Safety Recall R-2025-014

For each chain, the A and C entities are NEVER mentioned in the same fact:
the A->B edge and B->C edge are written as separate POST calls (different
facts, different sources below). This is what's enforced at ingestion time,
not just on paper -- the extractor can only invent a relation between
entities that co-occur in one call's content, so the only way a direct A->C
edge could appear is if a fact mentioned both, which none of the facts
below do (see the comments marking the bridge tuples).

A provenance-arbitration case is also engineered here: Cluster A's "Series A
funding round" amount is stated as "$42 million" by agent_finance and later
restated as "$45 million" by agent_pr -- same entity, conflicting property,
written by two different sources.
"""

import argparse
import os
import sys
from typing import Any

import httpx

# Display/label only -- the tenant a write lands in is now derived from the API
# key the client authenticates with, not sent in the request body.
TENANT_ID = "eval_test"

# (content, source)
CLUSTER_A_FACTS: list[tuple[str, str]] = [
    (
        "Dr. Sarah Chen and Dr. Marcus Webb co-founded Helios Therapeutics, "
        "a biotech startup developing treatments for pancreatic cancer.",
        "agent_research",
    ),
    (
        "Dr. Sarah Chen earned her PhD at Stanford University before "
        "co-founding Helios Therapeutics.",
        "agent_research",
    ),
    (
        "Dr. Marcus Webb completed his doctoral studies at the "
        "Massachusetts Institute of Technology.",
        "agent_research",
    ),
    (
        # Bridge A->B: Chen + the paper, no mention of RG-88/RiboGen. Kept
        # short and atomic (single clause, two entities), and the title is
        # NOT wrapped in single quotes -- a quoted title here was observed
        # to reliably (100% across 10 repeated calls) trip a tool-use
        # formatting bug in the underlying Anthropic call once the tenant
        # had accumulated enough distinct relation types for
        # _build_user_message's reuse hint to kick in (extractor.py);
        # dropping the quotes removed the trigger entirely (0/6 repeats).
        "Dr. Sarah Chen authored the paper CRISPR-X stability study while at Stanford University.",
        "agent_research",
    ),
    (
        "Helios Therapeutics' lead pipeline compound, HLX-203, is being "
        "developed specifically to target pancreatic cancer.",
        "agent_research",
    ),
    (
        # Provenance conflict setup (paired with the agent_pr fact below):
        # same entity, two sources, conflicting value for the same
        # property. Property NAMING is non-deterministic per-call (the
        # extractor isn't told what property name a prior call used, same
        # class of issue as the documented relation-type-naming variance --
        # see CLAUDE.md's "Property name non-determinism"), so this exact
        # "the amount raised was $X" phrasing was chosen because it was
        # verified to converge on the same `amount_raised` property key in
        # 7/8 repeated (fact1, fact2) pairs -- enough to lock in, not
        # because phrasing fully controls it. If a future re-seed lands on
        # a different shared key, update eval/dataset.yaml's provenance
        # case to match the real key (same pattern as the pre-existing
        # Globex/Product Y price-property note in that file).
        "Sequoia Capital and Atlas Venture both invested in Helios "
        "Therapeutics' Series A funding round; the amount raised was "
        "$42 million.",
        "agent_finance",
    ),
    (
        "Helios Therapeutics' Series A funding round amount raised was actually $45 million.",
        "agent_pr",
    ),
    (
        "HLX-203 received an FDA Orphan Drug Designation, recognizing its "
        "potential to treat a rare form of pancreatic cancer.",
        "agent_regulatory",
    ),
    (
        "RiboGen Inc, a rival biotech lab, is also targeting pancreatic "
        "cancer with its own compound, RG-88, putting it in direct "
        "competition with Helios Therapeutics' HLX-203.",
        "agent_competitive_intel",
    ),
    (
        "Dr. Elena Petrov leads the research team at RiboGen Inc that is developing RG-88.",
        "agent_competitive_intel",
    ),
    (
        # Bridge B->C: the paper + RG-88, no mention of Sarah Chen. RG-88 is
        # made the sentence subject (rather than "RiboGen Inc's scientists")
        # so the model reliably edges the paper directly to RG-88 instead of
        # to RiboGen Inc as an intermediate -- the original "cited by
        # RiboGen Inc's scientists ... developing RG-88" phrasing only
        # produced a direct paper->RG-88 edge in 5/8 repeats (RiboGen Inc
        # absorbed the edge instead in the other 3, stretching this to a
        # 3-hop chain); this phrasing was verified at 8/8.
        "RG-88's development was directly informed by findings published "
        "in CRISPR-X stability study.",
        "agent_competitive_intel",
    ),
    (
        "The Pancreatic Cancer Action Network announced a patient advocacy "
        "partnership with Helios Therapeutics.",
        "agent_ops",
    ),
]

CLUSTER_B_FACTS: list[tuple[str, str]] = [
    (
        "Dr. Amara Osei created and maintains the open source machine learning framework Cascade.",
        "agent_oss",
    ),
    ("Liang Wu is a core contributor to Cascade.", "agent_oss"),
    ("Dr. Amara Osei works at Vertex AI Labs.", "agent_oss"),
    ("Liang Wu works at Nordic Compute.", "agent_oss"),
    (
        "Dr. Amara Osei studied at UC Berkeley AI Research Lab before joining Vertex AI Labs.",
        "agent_oss",
    ),
    ("Liang Wu studied at Helsinki Polytechnic.", "agent_oss"),
    (
        # Bridge A->B: Osei + the whitepaper, no mention of AuroraML. Short,
        # unquoted title, no trailing participial clause -- see the comment
        # on Cluster A's CRISPR-X fact above for why titles aren't quoted;
        # this fact additionally needed the participial clause dropped
        # (verified: with it, this exact sentence still failed ~50% of
        # repeats once the tenant had many accumulated relation types;
        # without it, 0/6 failures).
        "Dr. Amara Osei authored the Cascade v3 architecture whitepaper.",
        "agent_oss",
    ),
    (
        # Bridge B->C: the whitepaper + AuroraML/Priya Nair, no mention of
        # Osei. Rephrased with Priya Nair/AuroraML as the lead subject
        # (verified 0/8 failures) after the original "whitepaper directly
        # influenced..." phrasing intermittently triggered the same
        # tool-use bug (~1/6 repeats) referenced above.
        "Priya Nair maintains AuroraML, a downstream library influenced by "
        "the Cascade v3 architecture whitepaper.",
        "agent_downstream",
    ),
    (
        "AuroraML depends on Cascade as its core computational backend.",
        "agent_downstream",
    ),
    (
        "Cascade is regularly evaluated on the MLPerf Training Benchmark.",
        "agent_oss",
    ),
    ("NeoSilicon sponsors the Cascade project.", "agent_vendor"),
    (
        "NeoSilicon's Quantix GPU hardware is optimized specifically for "
        "running Cascade workloads.",
        "agent_vendor",
    ),
    ("The Cascade Foundation governs the Cascade open source project.", "agent_oss"),
    (
        "Cascade v4.0 was released to patch a critical vulnerability tracked as CVE-2025-41122.",
        "agent_security",
    ),
]

CLUSTER_C_FACTS: list[tuple[str, str]] = [
    (
        "Vanta Battery Co is a tier-1 supplier that manufactures the Aegis "
        "Battery Pack for Solstice Motors.",
        "agent_procurement",
    ),
    (
        # Bridge A->B: Korrigan + the cell, no mention of the recall.
        "Korrigan Cells Ltd is a tier-2 supplier that produces the LFP-9 Cell.",
        "agent_procurement",
    ),
    (
        "The Aegis Battery Pack is built using LFP-9 Cells as its core component.",
        "agent_procurement",
    ),
    ("The Aegis Battery Pack holds ISO 26262 safety certification.", "agent_quality"),
    (
        "Solstice Motors assembles the Solstice EV-1 using the Aegis Battery Pack.",
        "agent_ops",
    ),
    (
        "Solstice Motors also produces the Solstice EV-2, a separate model "
        "that does not use the Aegis Battery Pack.",
        "agent_ops",
    ),
    (
        "Brightline Retail Group is the exclusive retail partner selling the Solstice EV-1.",
        "agent_retail",
    ),
    ("Meridian Auto Retailers sells the Solstice EV-2.", "agent_retail"),
    (
        "Harbor Logistics handles shipping for Solstice Motors' vehicles.",
        "agent_logistics",
    ),
    (
        "Port of Rotterdam congestion caused significant delays for Harbor Logistics shipments.",
        "agent_logistics",
    ),
    (
        "Vanta Battery Co experienced a Q3 2025 Cell Shortage that affected its production output.",
        "agent_quality",
    ),
    ("Raj Patel is the quality lead at Vanta Battery Co.", "agent_quality"),
    ("Tessa Lindqvist is the VP of Supply Chain at Solstice Motors.", "agent_ops"),
    (
        "Solstice Motors issued Voluntary Safety Recall R-2025-014 for the Solstice EV-1.",
        "agent_quality",
    ),
    (
        # Bridge B->C: the cell + the recall, no mention of Korrigan. Split
        # out from a single longer sentence that originally also mentioned
        # an intermediate "battery defect" concept -- that version put
        # LFP-9 Cell two hops from the recall (via the defect concept)
        # instead of one, breaking the engineered 2-hop chain. This atomic
        # form was verified to extract a direct LFP-9 Cell -> recall edge
        # reliably across 3 repeated calls.
        "The LFP-9 Cell was identified as the root cause of Solstice "
        "Motors' Voluntary Safety Recall R-2025-014.",
        "agent_quality",
    ),
]

CLUSTERS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Cluster A (Helios Therapeutics)", CLUSTER_A_FACTS),
    ("Cluster B (Cascade)", CLUSTER_B_FACTS),
    ("Cluster C (Solstice Motors)", CLUSTER_C_FACTS),
]


_MAX_ATTEMPTS = 5


def _post_memory(client: httpx.Client, content: str, source: str) -> dict[str, Any]:
    """POST one fact, retrying on transient 5xx failures.

    Observed in practice: the extraction call occasionally fails with a
    transient Anthropic/Instructor-level glitch (the model emitting two
    separate tool_use blocks instead of one, tripping a response_model
    validation error) that surfaces here as a 500. This is non-determinism
    in the underlying API call, not a problem with the fact's content --
    retrying the same content succeeds. Not the same thing as the
    "Property name non-determinism" and "Prompt non-determinism" issues
    that are out of scope to fix; this is a transport-level retry, same
    spirit as any other flaky-call handling.
    """
    last_exc: httpx.HTTPStatusError | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        response = client.post(
            "/v1/memories",
            json={"content": content, "source": source},
        )
        try:
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            print(f"  attempt {attempt}/{_MAX_ATTEMPTS} failed ({exc}), retrying...")
    assert last_exc is not None
    raise last_exc


def ingest(client: httpx.Client) -> None:
    for cluster_name, facts in CLUSTERS:
        print(f"\n=== {cluster_name}: {len(facts)} facts ===")
        for content, source in facts:
            memory = _post_memory(client, content, source)
            entity_names = [e["name"] for e in memory["entities"]]
            relation_count = len(memory["relations"])
            print(
                f"  [{source}] {len(entity_names)} entities, {relation_count} relations: {entity_names}"
            )


def print_graph_summary(client: httpx.Client) -> None:
    response = client.get("/v1/graph")
    response.raise_for_status()
    graph = response.json()
    entities = graph["entities"]
    relations = graph["relations"]

    connected_ids = {r["source_entity_id"] for r in relations} | {
        r["target_entity_id"] for r in relations
    }
    isolated = [e for e in entities if e["id"] not in connected_ids]

    print("\n=== Graph summary for tenant eval_test ===")
    print(f"total nodes: {len(entities)}")
    print(f"total edges: {len(relations)}")
    print(f"isolated nodes: {len(isolated)} ({len(isolated) / max(len(entities), 1):.1%})")
    if isolated:
        print("  isolated entity names:", [e["name"] for e in isolated])
    if entities and len(isolated) / len(entities) > 0.10:
        print(
            "  WARNING: isolated node rate exceeds 10% -- investigate "
            "extraction before writing eval cases.",
            file=sys.stderr,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Populate the eval_test tenant graph.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    api_key = os.getenv("CONTEXTSTORE_API_KEY")
    if not api_key:
        print(
            "CONTEXTSTORE_API_KEY is not set. The API now derives tenant_id from "
            "the API key; create a key bound to the eval tenant and export it.",
            file=sys.stderr,
        )
        return 1

    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(base_url=args.base_url, timeout=60.0, headers=headers) as client:
        ingest(client)
        print_graph_summary(client)

    return 0


if __name__ == "__main__":
    sys.exit(main())
