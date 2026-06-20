"""Eval harness: run dataset.yaml's cases against a live POST /v1/recall and
report hit rates, overall and per category.

Checks per case, all optional except entity presence:
  - entity presence:    every name in expected_entities appears in the result
  - property values:    expected_properties[entity][property] == actual value
  - relation values:    expected_relations[i] resolves to a real edge in the
                         result with the expected property value
  - forbidden entities:  none of forbidden_entities appears in the result
                         (cluster-isolation cases)
  - claim history:      expected_claim_history[entity] resolves to the right
                         sequence of claims, including supersession
                         (provenance-arbitration cases)

A case is a hit only if every check it declares passes. property/relation/
claim checks report actual vs. expected on mismatch, not just pass/fail --
that's the point of this extension (see README.md for why presence-only
checks missed a real bug). See README.md for how to add cases.

Per-case `limit` and `traversal_depth` override the --limit/--traversal-depth
CLI defaults (see dataset.yaml's bridging cases for why per-case `limit` is
needed: FalkorDB's small-graph HNSW under-return, Anomaly 3, means the
seed-friendly k differs per query on this graph size).

category: bridging is special-cased: the runner automatically runs the case
TWICE -- once at traversal_depth=1 (control, `bridge_target` must be ABSENT)
and once at traversal_depth=2 (target, normal entity-presence hit check,
`bridge_target` must be PRESENT) -- and reports both rows. This is automatic
based on category alone; bridging cases in dataset.yaml don't (and shouldn't)
set their own traversal_depth. A bridging case that finds bridge_target at
depth=1 is a poorly engineered case, not a passing one -- the control row's
hit reflects that directly.
"""

import argparse
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

EVAL_DIR = Path(__file__).parent
DEFAULT_DATASET = EVAL_DIR / "dataset.yaml"
DEFAULT_REPORTS_DIR = EVAL_DIR / "reports"


def load_cases(dataset_path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(dataset_path.read_text())
    cases: list[dict[str, Any]] = data["cases"]
    return cases


def check_entities(case: dict[str, Any], returned_names: set[str]) -> tuple[list[str], list[str]]:
    expected: list[str] = case.get("expected_entities", [])
    found = [name for name in expected if name in returned_names]
    missing = [name for name in expected if name not in returned_names]
    return found, missing


def check_properties(
    case: dict[str, Any], entities_by_name: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Compare expected_properties[entity][property] against the actual
    value returned for that entity. Returns one mismatch dict per failing
    (entity, property) pair, each carrying both the expected and actual
    value so a failure is legible without re-running anything by hand.
    """
    mismatches = []
    expected_properties: dict[str, dict[str, Any]] = case.get("expected_properties") or {}
    for entity_name, expected_props in expected_properties.items():
        entity = entities_by_name.get(entity_name)
        for property_name, expected_value in expected_props.items():
            actual_value = entity["properties"].get(property_name) if entity else None
            if entity is None or actual_value != expected_value:
                mismatches.append(
                    {
                        "entity": entity_name,
                        "property": property_name,
                        "expected": expected_value,
                        "actual": actual_value,
                    }
                )
    return mismatches


def check_relations(
    case: dict[str, Any], names_by_id: dict[str, str], relations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Compare expected_relations entries against the actual edges
    returned. Matches an expected entry to an edge by (source name, target
    name, relation_type), then compares the named property's value.
    """
    mismatches = []
    expected_relations: list[dict[str, Any]] = case.get("expected_relations") or []
    for expected in expected_relations:
        match = next(
            (
                relation
                for relation in relations
                if names_by_id.get(relation["source_entity_id"]) == expected["source"]
                and names_by_id.get(relation["target_entity_id"]) == expected["target"]
                and relation["relation_type"] == expected["relation_type"]
            ),
            None,
        )
        actual_value = match["properties"].get(expected["property"]) if match else None
        if match is None or actual_value != expected["expected_value"]:
            mismatches.append(
                {
                    "source": expected["source"],
                    "target": expected["target"],
                    "relation_type": expected["relation_type"],
                    "property": expected["property"],
                    "expected": expected["expected_value"],
                    "actual": actual_value,
                    "edge_found": match is not None,
                }
            )
    return mismatches


def check_forbidden_entities(case: dict[str, Any], returned_names: set[str]) -> list[str]:
    """Cluster-isolation check: none of forbidden_entities (named entities
    that belong to a different cluster) should appear in the result. Returns
    the ones that wrongly appeared.
    """
    forbidden: list[str] = case.get("forbidden_entities", [])
    return [name for name in forbidden if name in returned_names]


def check_claim_history(
    case: dict[str, Any], entities_by_name: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Provenance-arbitration check: expected_claim_history[entity] declares
    a property and an ordered list of {value, source, supersedes_previous?}
    claims that must all be present in that entity's actual `claims` list
    (Entity.claims, returned as part of /v1/recall's entities). Each
    declared claim must match on (property_name, value, provenance.source);
    one marked `supersedes_previous: true` must additionally carry a
    non-empty `provenance.supersedes`. This is checking the full claim
    history, not just the active (latest-wins) property value -- that's
    what check_properties already covers.
    """
    mismatches = []
    expected_history: dict[str, dict[str, Any]] = case.get("expected_claim_history") or {}
    for entity_name, spec in expected_history.items():
        entity = entities_by_name.get(entity_name)
        property_name = spec["property"]
        claims = [
            c for c in (entity["claims"] if entity else []) if c["property_name"] == property_name
        ]
        claims_by_value_source = {(c["value"], c["provenance"]["source"]): c for c in claims}
        for expected_claim in spec["values"]:
            key = (expected_claim["value"], expected_claim["source"])
            claim = claims_by_value_source.get(key)
            if claim is None:
                mismatches.append(
                    {
                        "entity": entity_name,
                        "property": property_name,
                        "expected_value": expected_claim["value"],
                        "expected_source": expected_claim["source"],
                        "issue": "claim_not_found",
                    }
                )
            elif expected_claim.get("supersedes_previous") and not claim["provenance"].get(
                "supersedes"
            ):
                mismatches.append(
                    {
                        "entity": entity_name,
                        "property": property_name,
                        "expected_value": expected_claim["value"],
                        "expected_source": expected_claim["source"],
                        "issue": "expected_supersession_not_recorded",
                    }
                )
    return mismatches


def _call_recall(
    client: httpx.Client, query: str, tenant_id: str, limit: int, traversal_depth: int
) -> tuple[dict[str, Any] | None, str | None]:
    # tenant_id is no longer sent in the body -- it's derived from the API key
    # the client authenticates with (see main()). It stays a parameter only for
    # report labelling consistency.
    try:
        response = client.post(
            "/v1/recall",
            json={
                "query": query,
                "limit": limit,
                "traversal_depth": traversal_depth,
            },
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return None, str(exc)
    return response.json(), None


def _empty_result(
    case_id: str, category: str, query: str, limit: int, traversal_depth: int, error: str | None
) -> dict[str, Any]:
    return {
        "id": case_id,
        "category": category,
        "query": query,
        "limit": limit,
        "traversal_depth": traversal_depth,
        "expected": [],
        "found": [],
        "missing": [],
        "returned_names": [],
        "property_mismatches": [],
        "relation_mismatches": [],
        "forbidden_found": [],
        "claim_mismatches": [],
        "hit": False,
        "error": error,
    }


def run_case(
    client: httpx.Client,
    case: dict[str, Any],
    tenant_id: str,
    default_limit: int,
    default_traversal_depth: int,
) -> dict[str, Any]:
    limit = case.get("limit", default_limit)
    traversal_depth = case.get("traversal_depth", default_traversal_depth)
    expected_entities: list[str] = case.get("expected_entities", [])

    result, error = _call_recall(client, case["query"], tenant_id, limit, traversal_depth)
    if result is None:
        out = _empty_result(
            case["id"], case["category"], case["query"], limit, traversal_depth, error
        )
        out["expected"] = expected_entities
        out["missing"] = expected_entities
        return out

    entities_by_name = {entity["name"]: entity for entity in result["entities"]}
    names_by_id = {entity["id"]: entity["name"] for entity in result["entities"]}
    returned_names = set(entities_by_name)

    found, missing = check_entities(case, returned_names)
    property_mismatches = check_properties(case, entities_by_name)
    relation_mismatches = check_relations(case, names_by_id, result["relations"])
    forbidden_found = check_forbidden_entities(case, returned_names)
    claim_mismatches = check_claim_history(case, entities_by_name)

    return {
        "id": case["id"],
        "category": case["category"],
        "query": case["query"],
        "limit": limit,
        "traversal_depth": traversal_depth,
        "expected": expected_entities,
        "found": found,
        "missing": missing,
        "returned_names": sorted(returned_names),
        "property_mismatches": property_mismatches,
        "relation_mismatches": relation_mismatches,
        "forbidden_found": forbidden_found,
        "claim_mismatches": claim_mismatches,
        "hit": not missing
        and not property_mismatches
        and not relation_mismatches
        and not forbidden_found
        and not claim_mismatches,
        "error": None,
    }


def run_bridging_case(
    client: httpx.Client, case: dict[str, Any], tenant_id: str, default_limit: int
) -> list[dict[str, Any]]:
    """Run a category: bridging case twice -- depth=1 control, depth=2
    target -- automatically, based on category alone (see module docstring).
    """
    limit = case.get("limit", default_limit)
    bridge_target: str = case["bridge_target"]

    control_result, control_error = _call_recall(client, case["query"], tenant_id, limit, 1)
    if control_result is None:
        control = _empty_result(
            f"{case['id']}@depth1", case["category"], case["query"], limit, 1, control_error
        )
    else:
        control_names = {entity["name"] for entity in control_result["entities"]}
        control_hit = bridge_target not in control_names
        control = {
            "id": f"{case['id']}@depth1",
            "category": case["category"],
            "query": case["query"],
            "limit": limit,
            "traversal_depth": 1,
            "expected": [],
            "found": [],
            "missing": [] if control_hit else [bridge_target],
            "returned_names": sorted(control_names),
            "property_mismatches": [],
            "relation_mismatches": [],
            "forbidden_found": [] if control_hit else [bridge_target],
            "claim_mismatches": [],
            "hit": control_hit,
            "error": None,
            "note": f"control: {bridge_target!r} must be ABSENT at depth=1 (else this case is mis-engineered)",
        }

    target = run_case(client, case, tenant_id, default_limit=limit, default_traversal_depth=2)
    target["id"] = f"{case['id']}@depth2"
    target["note"] = f"target: {bridge_target!r} must be PRESENT at depth=2"

    return [control, target]


def _format_mismatch_lines(result: dict[str, Any]) -> list[str]:
    lines = []
    if result["missing"]:
        lines.append(
            f"    missing entities: {result['missing']}  returned: {result['returned_names']}"
        )
    for mismatch in result["property_mismatches"]:
        lines.append(
            f"    property mismatch: {mismatch['entity']}.{mismatch['property']} "
            f"expected={mismatch['expected']!r} actual={mismatch['actual']!r}"
        )
    for mismatch in result["relation_mismatches"]:
        edge = f"{mismatch['source']} -[{mismatch['relation_type']}]-> {mismatch['target']}"
        if not mismatch["edge_found"]:
            lines.append(f"    relation mismatch: no edge {edge} found in result")
        else:
            lines.append(
                f"    relation mismatch: {edge}.{mismatch['property']} "
                f"expected={mismatch['expected']!r} actual={mismatch['actual']!r}"
            )
    if result.get("forbidden_found"):
        lines.append(f"    forbidden entities present: {result['forbidden_found']}")
    for mismatch in result["claim_mismatches"]:
        lines.append(
            f"    claim history mismatch: {mismatch['entity']}.{mismatch['property']} "
            f"expected claim value={mismatch['expected_value']!r} source={mismatch['expected_source']!r} "
            f"({mismatch['issue']})"
        )
    return lines


def print_table(results: list[dict[str, Any]]) -> None:
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        by_category[result["category"]].append(result)

    print(f"\n{'category':<24}{'hits':<10}{'rate':<8}")
    print("-" * 42)
    for category, rows in sorted(by_category.items()):
        hits = sum(row["hit"] for row in rows)
        print(f"{category:<24}{f'{hits}/{len(rows)}':<10}{hits / len(rows):.0%}")
    print("-" * 42)
    overall_hits = sum(row["hit"] for row in results)
    print(
        f"{'overall':<24}{f'{overall_hits}/{len(results)}':<10}{overall_hits / len(results):.0%}\n"
    )

    for result in results:
        status = "PASS" if result["hit"] else "FAIL"
        depth = result["traversal_depth"]
        print(
            f"[{status}] {result['id']} ({result['category']}, depth={depth}): {result['query']!r}"
        )
        if result.get("note"):
            print(f"    {result['note']}")
        if result["error"]:
            print(f"    error: {result['error']}")
        elif not result["hit"]:
            for line in _format_mismatch_lines(result):
                print(line)


def write_report(
    results: list[dict[str, Any]],
    reports_dir: Path,
    base_url: str,
    tenant_id: str,
    limit: int,
    traversal_depth: int,
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = reports_dir / f"{timestamp}.md"

    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        by_category[result["category"]].append(result)
    overall_hits = sum(row["hit"] for row in results)

    lines = [
        f"# ContextStore recall eval -- {timestamp}",
        "",
        f"- base_url: `{base_url}`",
        f"- tenant_id: `{tenant_id}`",
        f"- default limit: {limit}",
        f"- default traversal_depth: {traversal_depth}",
        "- (cases may override both per-case -- see dataset.yaml)",
        f"- cases: {len(results)}",
        "",
        "## Per-category hit rate",
        "",
        "| category | hits | rate |",
        "|---|---|---|",
    ]
    for category, rows in sorted(by_category.items()):
        hits = sum(row["hit"] for row in rows)
        lines.append(f"| {category} | {hits}/{len(rows)} | {hits / len(rows):.0%} |")
    lines.append(
        f"| **overall** | **{overall_hits}/{len(results)}** | **{overall_hits / len(results):.0%}** |"
    )

    lines += ["", "## Per-case detail", ""]
    for result in results:
        status = "PASS" if result["hit"] else "FAIL"
        lines.append(
            f"### [{status}] {result['id']} ({result['category']}, depth={result['traversal_depth']})"
        )
        lines.append("")
        lines.append(f"- query: {result['query']!r}")
        lines.append(f"- limit: {result['limit']}")
        if result.get("note"):
            lines.append(f"- note: {result['note']}")
        lines.append(f"- expected entities: {result['expected']}")
        lines.append(f"- found entities: {result['found']}")
        lines.append(f"- missing entities: {result['missing']}")
        lines.append(f"- returned_names: {result['returned_names']}")
        if result["property_mismatches"]:
            lines.append("- property mismatches:")
            for mismatch in result["property_mismatches"]:
                lines.append(
                    f"  - {mismatch['entity']}.{mismatch['property']}: "
                    f"expected={mismatch['expected']!r} actual={mismatch['actual']!r}"
                )
        if result["relation_mismatches"]:
            lines.append("- relation mismatches:")
            for mismatch in result["relation_mismatches"]:
                edge = f"{mismatch['source']} -[{mismatch['relation_type']}]-> {mismatch['target']}"
                lines.append(
                    f"  - {edge}.{mismatch['property']}: expected={mismatch['expected']!r} "
                    f"actual={mismatch['actual']!r} (edge_found={mismatch['edge_found']})"
                )
        if result.get("forbidden_found"):
            lines.append(f"- forbidden entities present: {result['forbidden_found']}")
        if result["claim_mismatches"]:
            lines.append("- claim history mismatches:")
            for mismatch in result["claim_mismatches"]:
                lines.append(
                    f"  - {mismatch['entity']}.{mismatch['property']}: expected claim "
                    f"value={mismatch['expected_value']!r} source={mismatch['expected_source']!r} "
                    f"({mismatch['issue']})"
                )
        if result["error"]:
            lines.append(f"- error: {result['error']}")
        lines.append("")

    report_path.write_text("\n".join(lines))
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ContextStore recall eval harness.")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="FastAPI base URL (default: %(default)s)",
    )
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="Path to dataset.yaml")
    parser.add_argument("--tenant-id", default="eval_test")
    parser.add_argument("--limit", type=int, default=10, help="Default limit; cases may override")
    parser.add_argument(
        "--traversal-depth", type=int, default=1, help="Default traversal_depth; cases may override"
    )
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR))
    args = parser.parse_args()

    cases = load_cases(Path(args.dataset))
    if not cases:
        print("No cases found in dataset.", file=sys.stderr)
        return 1

    api_key = os.getenv("CONTEXTSTORE_API_KEY")
    if not api_key:
        print(
            "CONTEXTSTORE_API_KEY is not set. The API now derives tenant_id from "
            "the API key; create a key bound to the eval tenant and export it.",
            file=sys.stderr,
        )
        return 1

    results: list[dict[str, Any]] = []
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(base_url=args.base_url, timeout=30.0, headers=headers) as client:
        for case in cases:
            if case["category"] == "bridging":
                results.extend(run_bridging_case(client, case, args.tenant_id, args.limit))
            else:
                results.append(
                    run_case(client, case, args.tenant_id, args.limit, args.traversal_depth)
                )

    print_table(results)
    report_path = write_report(
        results,
        Path(args.reports_dir),
        args.base_url,
        args.tenant_id,
        args.limit,
        args.traversal_depth,
    )
    print(f"Report written to {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
