"""Claim: a single source's assertion, optionally about one entity/relation
property. Entities and relations keep a full list of claims (see
`Entity.claims` / `Relation.claims`) so that multiple, possibly conflicting,
writers are preserved instead of the first or last writer silently winning.

`apply_claim` and `derive_active_view` are the two operations every merge
site (entity resolution, relation write) needs: append this write's claim(s)
to the history, then derive the backward-compatible single-value view
(`properties`, `provenance`) that existing callers (including the frontend)
already read.
"""

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from contextstore.models.provenance import Provenance


class Claim(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    property_name: str | None = None
    value: Any | None = None
    provenance: Provenance


def _active_claim(claims: list[Claim], property_name: str) -> Claim | None:
    """Most recent non-superseded claim for `property_name`, or None."""
    superseded_ids = {
        UUID(claim_id) for claim in claims for claim_id in (claim.provenance.supersedes or [])
    }
    candidates = [
        claim
        for claim in claims
        if claim.property_name == property_name and claim.id not in superseded_ids
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda claim: claim.provenance.created_at)


def apply_claim(
    claims: list[Claim],
    provenance: Provenance,
    properties: dict[str, Any],
) -> list[Claim]:
    """Append the claim(s) for one write's touch of an entity/relation.

    One claim per asserted property. If no properties were asserted, a
    single `property_name=None` claim still records that this source
    touched the entity/relation, so `contributing_sources` reflects every
    writer, not just ones that asserted a property value.

    When an asserted property's value differs from the currently active
    claim's value for that property, the prior claim is marked superseded
    via `provenance.supersedes` -- it is never removed from the list.
    "Different value" triggers supersession regardless of whether the new
    claim's source matches the old one's (a source can revise its own
    earlier claim, not just be overridden by another source).
    """
    updated = list(claims)

    if not properties:
        updated.append(Claim(provenance=provenance))
        return updated

    for property_name, value in properties.items():
        active = _active_claim(updated, property_name)
        claim_provenance = provenance
        if active is not None and active.value != value:
            claim_provenance = provenance.model_copy(
                update={"supersedes": [*(provenance.supersedes or []), str(active.id)]}
            )
        updated.append(
            Claim(property_name=property_name, value=value, provenance=claim_provenance)
        )

    return updated


def derive_active_view(claims: list[Claim]) -> tuple[dict[str, Any], Provenance, list[str]]:
    """Compute the backward-compatible (properties, provenance, contributing_sources)
    view from a full claim history.

    `properties` and `provenance` resolve to the latest-claim-wins active
    value (per the default "no conflict resolution beyond recency" policy);
    `contributing_sources` is every distinct source that has ever made a
    claim, including ones that only ever corroborated an existing value.
    """
    property_names = {claim.property_name for claim in claims if claim.property_name is not None}
    properties: dict[str, Any] = {}
    for property_name in property_names:
        active = _active_claim(claims, property_name)
        if active is not None:
            properties[property_name] = active.value

    contributing_sources = sorted({claim.provenance.source for claim in claims})

    if not claims:
        # Should not occur in practice -- every Entity/Relation gets at
        # least one claim via apply_claim() on creation.
        return properties, Provenance(source="unknown"), contributing_sources

    latest = max(claims, key=lambda claim: claim.provenance.created_at)
    return properties, latest.provenance, contributing_sources
