# 2. One FalkorDB graph per tenant, not a property filter

## Status

Accepted.

## Context

Every `Scope` already carries a `tenant_id`-equivalent set of keys for
addressing memories (see `docs/architecture.md`'s Scope section). The
question is *how* tenant isolation is enforced at the storage layer, now
that entity embeddings live in FalkorDB (see [1. FalkorDB native vector
index](0001-falkordb-native-vector-index.md)).

FalkorDB's own documentation states plainly: vector queries don't combine
well with property filters
(https://docs.falkordb.com/cypher/indexing/vector-index.html). This was
also checked live: a post-`YIELD` `WHERE node.entity_type = $x` filter on
`db.idx.vector.queryNodes` results does work *syntactically*, but that's
not the real problem. The real problem is that the underlying ANN search
still runs across the *entire* index before any filter is applied. In a
single shared graph holding multiple tenants' entities, the top-`k`
nearest neighbors returned by the vector index could be dominated
entirely by other tenants' data, leaving a tenant's own query with zero
results after filtering -- a correctness and availability problem, not
just a performance one. Filtering after retrieval cannot guarantee a
tenant gets any of its own data back.

## Decision

Every `Scope` requires a mandatory `tenant_id`. `FalkorDBGraphStore`
selects or creates a FalkorDB graph named `tenant_<tenant_id>` per
tenant -- a fully separate FalkorDB graph, not a label or property. A
vector search inside that graph structurally cannot return another
tenant's entities, because they don't exist in that graph at all.

All other scope keys (`user_id`, `project`, `agent_id`, `workflow_id`,
etc.) remain node/relation properties *within* a tenant's graph, and are
filtered in application code after retrieval (see
`FalkorDBGraphStore.find_entities` / `find_similar_entities` /
`traverse`). This is fine because per-tenant result sets are expected to
stay small for a long time -- the failure mode that motivated structural
isolation (a shared top-k window dominated by other tenants) doesn't
apply to filtering within one tenant's own, much smaller dataset.

`Scope.includes()` also independently enforces that two scopes can only
include one another if `tenant_id` matches, so this isolation is
defense-in-depth at the model layer too, not just the storage layer.

## Consequences

- `get_entity` and `delete_memory` on the `GraphStore` interface take an
  explicit `tenant_id` parameter (in addition to operations that already
  carry a `Scope`), since they address a single entity/memory by id and
  need to know which graph to look in.
- `tenant_id` is restricted to a safe slug charset (`^[A-Za-z0-9_-]+$`)
  since it's used directly as a FalkorDB graph name.
- No cross-tenant queries are possible at all through `GraphStore` --
  there's no method that takes more than one tenant at a time. Any future
  cross-tenant feature (e.g. platform-level analytics) needs a
  deliberately separate code path, not a parameter tweak.
- Each tenant's graph needs its own vector index, created via
  `ensure_graph_initialized` -- this is called at the start of every
  `remember()` write rather than once at provisioning time, since there's
  no separate tenant-provisioning step yet.
- This was the one piece of the build explicitly verified against a live
  FalkorDB instance with an integration test
  (`test_tenant_isolation_is_structural` in
  `tests/integration/test_falkordb_store.py`) rather than just reasoned
  about, given how much the rest of the system's correctness depends on
  it holding.
