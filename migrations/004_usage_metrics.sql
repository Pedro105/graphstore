-- Recall metrics on the usage log.
--
-- RetrievalStats (total_ms, query_class) is computed on every /v1/recall but was
-- discarded once the response was sent. These two nullable columns persist it on
-- the existing per-request event log -- the natural grain (one row per recall,
-- already carrying created_at/tenant_id/endpoint) -- so the admin analytics view
-- can show latency p50/p95 trends and query-class breakdowns over time without a
-- separate table or a join. Nullable: /v1/memories rows simply leave them empty,
-- and every existing row stays valid.
--
--   psql "$DATABASE_URL" -f migrations/004_usage_metrics.sql

ALTER TABLE usage_log ADD COLUMN latency_ms INT;       -- end-to-end recall latency (RetrievalStats.total_ms)
ALTER TABLE usage_log ADD COLUMN query_class TEXT;     -- classifier class, or "manual" when routing was pinned

-- Time-series + breakdown reads filter on (endpoint, created_at) and group by
-- day / query_class; this supports the "recall latency & class over time" panels.
CREATE INDEX ON usage_log (endpoint, created_at);
