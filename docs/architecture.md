# Architecture

## What this is

A GraphRAG-based memory layer for AI workflows. Multiple agents, scheduled
jobs, or AI features within a product can write structured knowledge to a
shared store and query it via hybrid vector + graph retrieval. The store
maintains provenance, handles conflicts, and supports scoped access.

The hypothesis: AI workflows that operate over time (multi-agent pipelines,
scheduled jobs, multi-feature SaaS products) generate query shapes that
vector-only retrieval handles poorly — multi-hop relational queries,
provenance-aware queries, and queries that require structural reasoning
about entities and their relationships. A GraphRAG-native memory layer with
strong scoping and provenance support fills this gap.

## Why this exists

Existing memory tools (Mem0, Zep, Letta) are optimized for conversational
personalization. They model memory as facts about users that compound across
chat sessions. This abstraction breaks down when:

- Multiple agents need to write to and read from a shared knowledge store
- The "user" is a workflow or pipeline, not a person
- Queries are relational and multi-hop, not similarity-based
- Provenance and conflict resolution matter as primary features
- Multiple AI features within one product need shared context

The wedge is workflow-shaped memory, not conversation-shaped memory.

## What this is not

- Not a chatbot memory tool (Mem0 covers that)
- Not a temporal reasoning system (Zep covers that)
- Not a stateful agent runtime (Letta covers that)
- Not a vector database (pgvector and Pinecone cover that)
- Not a graph database (FalkorDB and Neo4j cover that)
- Not an agent framework (LangGraph and CrewAI cover that)

This sits between agent frameworks and the underlying stores. It is the
memory and knowledge layer that agents read and write through.

## Core concepts

### Memory

The atomic unit. A piece of structured knowledge with content, scope,
source, timestamp, confidence, and supersession chain.

### Scope

The hierarchical addressing model. A scope is a dictionary of key-value
pairs that locates a memory in a logical space. `tenant_id` is mandatory
and always the first key — it selects which FalkorDB graph a memory lives
in (see "Tenant isolation" below). Examples:

- `{"tenant_id": "acme", "user_id": "u_123"}` — personal memory
- `{"tenant_id": "acme", "workflow_id": "nightly_triage", "run_id": "2026-06-15"}` — workflow state
- `{"tenant_id": "acme", "project": "research_alpha", "agent_id": "researcher_1"}` — agent memory

Scopes are hierarchical and composable beneath a shared tenant. Reads
respect scope inclusion: a read with `{"tenant_id": "acme", "project":
"alpha"}` returns memories tagged with that project regardless of
agent_id within it, but never crosses into another tenant's data.

### Tenant isolation

FalkorDB's vector search doesn't combine well with property filters (see
`docs/decisions/` for the ADR), so tenant isolation can't rely on
filtering inside a vector query. Instead, every tenant gets its own
FalkorDB graph, selected by `tenant_id`. A vector search inside that graph
structurally cannot leak another tenant's data. All other scope keys
remain node/relation properties within the tenant's graph, filtered in
application code after retrieval.

### Entity and Relation

Memories are decomposed at write time into entities (people, things,
concepts) and typed relationships between them. These form a property
graph stored in FalkorDB.

### Provenance

Every memory tracks who wrote it (agent ID, process, or user), when, with
what confidence, and what evidence supports it. Every memory can supersede
prior memories, forming a version chain.

### Hybrid retrieval

Recall combines vector similarity (for finding relevant entry points) with
graph traversal (for multi-hop relational queries). A query classifier
routes between strategies based on query shape.

## High-level architecture

[Agent or developer code]

│

▼

[Python SDK / TypeScript SDK / MCP server / REST API]

│

▼

[FastAPI service layer]

│

▼

[Core domain service]

│

├─ Extraction (LLM-based, async via arq workers)

├─ Entity resolution (embedding similarity + property matching)

├─ Conflict resolution and supersession

├─ Hybrid retrieval (vector + graph)

└─ Provenance tracking

│

├─────────────► FalkorDB (graph: entities, relations, embeddings on nodes)

├─────────────► Postgres + pgvector (vectors, users, billing, audit)

├─────────────► Cloudflare R2 (raw source documents)

└─────────────► LLM providers (Anthropic, OpenAI via LiteLLM)

## Module boundaries

- `api/` — HTTP routing, authentication, request/response shaping. No business logic.
- `models/` — pydantic schemas. The stable contracts between modules.
- `extraction/` — natural language to entities and relations via LLM.
- `resolution/` — entity disambiguation and conflict resolution.
- `graph/` — FalkorDB abstraction. Cypher queries are confined here.
- `vector/` — pgvector abstraction and embedding generation.
- `retrieval/` — query routing, traversal, scoring, hybrid fusion.
- `core/` — orchestration. The service that the API calls into.
- `llm/` — provider-agnostic LLM client via LiteLLM.
- `workers/` — background jobs for async extraction and maintenance.

Crossing module boundaries is only allowed via pydantic models defined in
`models/`. This is the discipline that lets the project scale without
turning into mud.

## API contract (v1)

Three core operations, plus utility methods. See `docs/api-contract.md` for
the full specification.

```python
# Write
store.remember(
    content: str,
    scope: dict,
    source: str | None = None,
    confidence: float = 1.0,
    evidence: list[str] | None = None,
) -> Memory

# Read
store.recall(
    query: str,
    scope: dict,
    limit: int = 10,
    traversal_depth: int = 1,
    include_superseded: bool = False,
) -> list[RecallResult]

# Inspect
store.list(scope: dict, limit: int = 100) -> list[Memory]
store.get(memory_id: str) -> Memory
store.forget(memory_id: str) -> None
```

All methods return pydantic models with full provenance and confidence
exposed. Developers integrate against these fields from day one even if
the v1 implementation populates them with simple defaults.

## What's in scope for v1

- Single-LLM-provider extraction (Claude Haiku for cost reasons)
- Binary relation extraction (subject-predicate-object triples)
- Entity resolution via embedding similarity + exact property matching
- Basic conflict detection (same subject-predicate, different object) with
  supersession marking
- Hybrid retrieval: vector seed + graph one-hop expansion
- Scope-based access control
- Provenance fields on every memory
- Python SDK
- MCP server
- REST API with OpenAPI spec
- Web dashboard with table view and basic graph visualization

## What's explicitly deferred

- Multi-LLM provider routing (LiteLLM is wired but only Anthropic active)
- N-ary relation extraction
- Learned entity resolution (LLM verification only as fallback)
- Multi-hop graph traversal beyond depth 1
- Community detection / hierarchical summarization (Microsoft GraphRAG style)
- Learned query router (heuristic classification only)
- Temporal validity windows on facts
- TypeScript SDK
- Self-hosted distribution with Docker Compose for end users
- Advanced graph visualization (force-directed, timeline scrubbing)
- Enterprise features (SSO, audit log export, on-prem deployment)

## Known hard problems

These are the parts of the system where success or failure is determined.
They get disproportionate attention during the build.

### Entity disambiguation

The most likely source of schedule overrun. When agent A writes about
"Pedro Costa" and agent B writes about "P. Costa", are they the same
entity? The v1 approach combines embedding similarity, exact property
matching, and type constraints. Failure mode: fragmented entities lead to
fragmented retrieval, which degrades the entire product.

Mitigation: store "merge candidates" on every entity so that improved
disambiguation can retroactively merge without data loss. Instrument
heavily so users can see and report disambiguation errors.

### Relation deduplication

Separate from and simpler than entity disambiguation above. Two
independent `remember()` calls that each state the same fact between the
same two (already-resolved) entities — e.g. two sentences that both say
"Pedro works at ASML" — must not produce two edges. Relations are
deduplicated at write time via a graph `MERGE` keyed on
`(source_entity_id, target_entity_id, relation_type)`, not on relation
properties or vector similarity. First write creates the edge with
`support_count=1`; every repeat increments `support_count` and updates
`last_seen`, leaving the original id/provenance untouched. Multi-source
provenance (tracking *which* memories support a relation, not just how
many) is future scope.

### Conflict arbitration

When two agents write contradictory facts about the same entity, which
wins? V1 uses recency (latest wins) plus explicit supersession. V2 may
add confidence-weighted arbitration and multi-source consensus.

### Cost of write-time extraction

Every `remember` call costs an LLM call. At scale this is significant.
Mitigation: batch when possible, support async writes, fall back to
cheaper models when the input is short.

### Retrieval quality on multi-hop queries

The KET-RAG study found that even when GraphRAG retrieves the right
context, 73-84% of errors are reasoning failures, not retrieval failures.
Mitigation: structured prompting in retrieval output (SPARQL-style chain
of thought) and graph-walk compression of returned context.

## Build approach

We are building production code from day one, not validating with a
spike — the literature already establishes that GraphRAG wins on
multi-hop relational queries, which is the target use case here. The
build favors strong type discipline (pydantic at module boundaries,
`mypy --strict`), integration tests against a real FalkorDB instance
rather than mocks, and module-by-module verification before wiring
modules together.

## Open architectural questions

These are decisions deferred until more information is available. Each
will eventually become an ADR.

- Graph schema: open-vocabulary relations vs constrained ontology vs hybrid?
- Embedding model versioning and re-embedding strategy
- Multi-tenant isolation: schema-per-tenant vs row-level security
- Cache layer: do we need Redis caching of frequent recalls?
- Pricing model: per-memory-written, per-recall, hybrid?

## References

- Microsoft GraphRAG (Edge et al., 2024) — original GraphRAG paper
- Mem0 (arXiv:2504.19413) — competitor, conversational memory benchmark
- Graphiti / Zep — closest existing tool, temporal focus
- GraphRAG-Bench (Xiao et al., 2025) — when GraphRAG helps
- KET-RAG reasoning bottleneck (Zarrinkia et al., 2026) — why retrieval is not enough
- MemGraphRAG (May 2026) — multi-agent for graph construction
- FalkorDB docs — primary graph store
