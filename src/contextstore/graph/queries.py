"""Cypher for the reified-claim model, kept out of falkordb_store.py so the
store reads as orchestration over named queries.

Reification means the predicate is a `:Claim` node *property*, not the Cypher
edge type -- the only edge types are the fixed `:SUBJECT` / `:OBJECT`, so none
of these need a relation type inlined into the string (unlike the old direct-edge
writes). They are all fully parameterized.
"""

# Upsert a claim node by id (create-or-update: status transitions reuse this),
# then ensure its structural edges to subject/object exist. MERGE on {id} only,
# SET the rest -- same shape as the entity write. The edge MERGEs are idempotent,
# so re-upserting an existing claim does not duplicate them.
UPSERT_CLAIM = """
MERGE (c:Claim {id: $id})
SET c += $props
WITH c
MATCH (s:Entity {id: $subject_id})
MATCH (o:Entity {id: $object_id})
MERGE (c)-[:SUBJECT]->(s)
MERGE (c)-[:OBJECT]->(o)
"""

# Candidate conflicting/corroborating claims: same subject, same normalized
# predicate, currently active. (Disputed claims are not re-adjudicated here.)
FIND_ACTIVE_CLAIMS = """
MATCH (c:Claim)-[:SUBJECT]->(:Entity {id: $subject_id})
WHERE c.status = 'active' AND c.predicate = $predicate
RETURN c
"""

# Collapse projection: every live (active or disputed) claim as a subject->object
# pair. The single source of display edges for both GET /v1/graph and recall.
PROJECT_LIVE_CLAIMS = """
MATCH (c:Claim)-[:SUBJECT]->(s:Entity)
MATCH (c)-[:OBJECT]->(o:Entity)
WHERE c.status IN ['active', 'disputed']
RETURN c, s.id, o.id
"""

# One BFS hop through live claims, treating a claim as a logical edge between its
# two entities. Both directions are reachable (claims are matched from either
# endpoint); n.id <> e.id drops the degenerate same-endpoint binding.
FETCH_CLAIM_NEIGHBOURS = """
MATCH (e:Entity)<-[:SUBJECT|OBJECT]-(c:Claim)-[:SUBJECT|OBJECT]->(n:Entity)
WHERE e.id IN $frontier_ids AND c.status IN ['active', 'disputed'] AND n.id <> e.id
RETURN DISTINCT n, c
"""

# Distinct predicates in a tenant's live graph -- biases extraction toward
# reusing an existing relation vocabulary (replaces the old traverse-based scan).
DISTINCT_PREDICATES = """
MATCH (c:Claim)
WHERE c.status IN ['active', 'disputed']
RETURN DISTINCT c.raw_predicate AS predicate
"""

# Live claims incident to a set of entities, for the claim-aware traverse()
# (graph snapshot / admin view).
CLAIMS_INCIDENT_TO = """
MATCH (c:Claim)-[:SUBJECT]->(s:Entity)
MATCH (c)-[:OBJECT]->(o:Entity)
WHERE (s.id IN $entity_ids OR o.id IN $entity_ids) AND c.status IN ['active', 'disputed']
RETURN c, s.id, o.id
"""

# Delete the claims incident to an entity along with the entity (entity delete
# must not leave orphaned :Claim nodes behind).
DELETE_ENTITY_WITH_CLAIMS = """
MATCH (n:Entity {id: $id})
OPTIONAL MATCH (c:Claim)-[:SUBJECT|OBJECT]->(n)
DETACH DELETE c, n
"""

# Same, but for every entity written by a given memory.
DELETE_MEMORY_WITH_CLAIMS = """
MATCH (n:Entity {memory_id: $memory_id})
OPTIONAL MATCH (c:Claim)-[:SUBJECT|OBJECT]->(n)
DETACH DELETE c, n
"""

# Count entities and live claims for a tenant (admin/per-project stats).
COUNT_ENTITIES = "MATCH (n:Entity) RETURN count(n)"
COUNT_LIVE_CLAIMS = "MATCH (c:Claim) WHERE c.status IN ['active', 'disputed'] RETURN count(c)"

# Disputed claims -- the unresolved cross-asserter conflicts, for the inspection
# endpoint / MCP tool (Stage 3: surface the wedge).
DISPUTED_CLAIMS = "MATCH (c:Claim) WHERE c.status = 'disputed' RETURN c"
