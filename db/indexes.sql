-- =============================================================================
-- XenoPulse :: Production secondary indexes
-- =============================================================================
-- Kept separate from schema.sql so the Query Performance Lab can DROP / CREATE
-- specific indexes at runtime and benchmark real EXPLAIN (ANALYZE, BUFFERS)
-- output before vs after.
--
-- Rationale per index is in the comment above it. These are the indexes a
-- production deployment of this workload actually needs -- no "index everything".
-- =============================================================================

-- orders -----------------------------------------------------------------------
-- Almost every customer-level analysis filters/join on customer_id.
CREATE INDEX IF NOT EXISTS ix_orders_customer_id
    ON orders (customer_id);

-- Revenue trend, cohort and freshness queries range-scan on order_date.
CREATE INDEX IF NOT EXISTS ix_orders_order_date
    ON orders (order_date);

-- Dashboard revenue = completed orders only; partial index keeps it small and
-- lets the planner do an index-only style scan for the hot path.
CREATE INDEX IF NOT EXISTS ix_orders_completed_date
    ON orders (order_date)
    WHERE status = 'completed';

-- Campaign attribution / conversion-rate joins.
CREATE INDEX IF NOT EXISTS ix_orders_campaign_id
    ON orders (campaign_id)
    WHERE campaign_id IS NOT NULL;

-- Covering index for the "customer lifetime value" aggregation so it can run
-- index-only (no heap fetch) -- used in the aggregation-optimisation demo.
CREATE INDEX IF NOT EXISTS ix_orders_cust_status_incl
    ON orders (customer_id, status)
    INCLUDE (net_amount, order_date);

-- order_items ----------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_order_items_order_id
    ON order_items (order_id);

CREATE INDEX IF NOT EXISTS ix_order_items_product_id
    ON order_items (product_id);

-- campaign_events (the big table) ------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_campaign_events_campaign_id
    ON campaign_events (campaign_id);

CREATE INDEX IF NOT EXISTS ix_campaign_events_customer_id
    ON campaign_events (customer_id);

-- Funnel counts filter on event_type and bucket by event_time. Composite +
-- INCLUDE(revenue) makes "revenue by campaign for converts" index-only.
CREATE INDEX IF NOT EXISTS ix_campaign_events_type_time
    ON campaign_events (event_type, event_time)
    INCLUDE (campaign_id, revenue);

-- customers ------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_customers_signup_date
    ON customers (signup_date);

CREATE INDEX IF NOT EXISTS ix_customers_acquisition_channel
    ON customers (acquisition_channel);

ANALYZE;
