"""Scope: the hierarchical addressing model for memories, entities, and relations."""

import re
from typing import cast

from pydantic import RootModel, field_validator

ScopeValue = str | int | float | bool

# tenant_id is used directly as a FalkorDB graph name (a Redis key), so it's
# restricted to a safe slug charset rather than allowing arbitrary strings.
_SAFE_TENANT_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class Scope(RootModel[dict[str, ScopeValue]]):
    """A key-value mapping that locates a memory in a logical space.

    `tenant_id` is mandatory on every scope: FalkorDB's vector search doesn't
    combine well with property filters, so tenant isolation is enforced
    structurally (one FalkorDB graph per tenant) rather than by filtering.
    All other scope keys (user_id, project, agent_id, ...) are filtered in
    application code after retrieval.

    Scopes are otherwise hierarchical and composable: a broader scope
    `includes` a narrower one if every key-value pair in the broader scope
    is also present in the narrower one, and both share the same tenant_id.
    E.g. `{"tenant_id": "acme", "project": "alpha"}` includes
    `{"tenant_id": "acme", "project": "alpha", "agent_id": "researcher_1"}`.
    """

    @field_validator("root")
    @classmethod
    def _validate(cls, value: dict[str, ScopeValue]) -> dict[str, ScopeValue]:
        if "tenant_id" not in value:
            raise ValueError("scope must contain a 'tenant_id' key")
        tenant_id = value["tenant_id"]
        if not isinstance(tenant_id, str) or not _SAFE_TENANT_ID.match(tenant_id):
            raise ValueError(
                f"tenant_id {tenant_id!r} must be a non-empty string matching "
                "^[A-Za-z0-9_-]+$ (used directly as a FalkorDB graph name)"
            )
        for key in value:
            if not key:
                raise ValueError("scope keys must be non-empty strings")
        return value

    @property
    def tenant_id(self) -> str:
        return cast(str, self.root["tenant_id"])

    def includes(self, other: "Scope") -> bool:
        """Return True if `other` is at least as specific as this scope.

        Always False across tenants, regardless of other keys.
        """
        if self.tenant_id != other.tenant_id:
            return False
        return all(other.root.get(key) == val for key, val in self.root.items())

    def to_query_dict(self) -> dict[str, ScopeValue]:
        return dict(self.root)

    @classmethod
    def from_dict(cls, data: dict[str, ScopeValue]) -> "Scope":
        return cls(data)
