# 1. Use FalkorDB's native vector index instead of Postgres + pgvector

## Status

Accepted.

## Context

`docs/architecture.md`'s original high-level architecture put entity
embeddings in Postgres + pgvector, alongside users, billing, and audit
data, with FalkorDB holding only graph structure. Building the core
write/read engine required picking a concrete vector storage approach
for entity embeddings now, not deferring it.

FalkorDB ships a native vector index (HNSW-based) as of recent versions:
`CREATE VECTOR INDEX FOR (label) ON (attribute) OPTIONS {...}`, with
`vecf32()` to construct vector literals and `CALL
db.idx.vector.queryNodes(...) YIELD node, score` to search. See
https://docs.falkordb.com/cypher/indexing/vector-index.html.

## Decision

Use FalkorDB's native vector index for entity embeddings. Skip
Postgres/pgvector for this phase. Embeddings are stored directly as a
property on `:Entity` nodes (written via `vecf32()`), and similarity
search happens via `db.idx.vector.queryNodes` in the same graph that
holds the entities.

This was verified live against a local FalkorDB instance before
implementation, not assumed from the docs alone:

- Index creation, `vecf32()`, and `db.idx.vector.queryNodes` all work as
  documented, including parameterized `OPTIONS` (dimension,
  similarityFunction) and parameterized label/attribute/k/vector
  arguments to the query procedure.
- **Score is cosine distance, not similarity** (0 = identical, 1 =
  unrelated) -- confirmed empirically (identical vectors scored 0.0,
  orthogonal vectors scored 1.0), contrary to the more common "higher
  score = more similar" convention. `FalkorDBGraphStore.find_similar_entities`
  converts this to similarity (`1 - distance`) before returning, so the
  rest of the system (config thresholds, entity resolution) works in the
  usual "higher = more similar" convention.
- **Embeddings must be written via `vecf32()` in a dedicated `SET`
  clause.** Setting a plain list as part of a bulk property merge (`SET n
  += {embedding: [...]}`) is silently invisible to the vector index, even
  though it round-trips fine as an ordinary property. This is easy to get
  wrong silently, so `FalkorDBGraphStore` always issues a distinct
  `SET n.embedding = vecf32($embedding)`.
- Duplicate index creation raises a catchable error (`"Attribute
  'embedding' is already indexed"`), used to make
  `ensure_graph_initialized` idempotent.

## Consequences

- One fewer system to run and operate for this phase (no Postgres).
- Entities and their embeddings live in the same store, so resolution
  (`resolution/entity_resolver.py`) and recall don't need a cross-store
  join between graph and vector data.
- Revisiting this later (e.g. if FalkorDB's vector index doesn't scale to
  the embedding volume we need, or if pgvector's filtering support
  becomes worth the extra system) is still open -- see
  `docs/architecture.md`'s "Open architectural questions".
- This decision is entangled with [2. Graph-per-tenant
  isolation](0002-graph-per-tenant-isolation.md): FalkorDB's vector
  search doesn't combine well with property filters, which is what
  forced tenant isolation to be structural rather than a query filter.
