-- =============================================================================
-- XenoPulse :: Partitioning demo
-- =============================================================================
-- Builds campaign_events_part: a RANGE-partitioned-by-month copy of
-- campaign_events. The Query Performance Lab uses it to show partition pruning:
-- a time-bounded query touches 1-2 partitions instead of scanning the whole
-- table.
--
-- Run AFTER seed.sql. Safe to re-run (drops + rebuilds).
-- Adds ~2M rows; runs in a few seconds.
-- =============================================================================

SET client_min_messages = warning;

DROP TABLE IF EXISTS campaign_events_part CASCADE;

CREATE TABLE campaign_events_part (
    event_id    BIGINT      NOT NULL,
    campaign_id BIGINT      NOT NULL,
    customer_id BIGINT      NOT NULL,
    event_type  TEXT        NOT NULL,
    event_time  TIMESTAMPTZ NOT NULL,
    order_id    BIGINT,
    revenue     NUMERIC(12,2) NOT NULL DEFAULT 0
) PARTITION BY RANGE (event_time);

-- Monthly partitions covering the seeded range (2022-01 .. 2026-01).
DO $$
DECLARE
    d date := date '2022-01-01';
    stop date := date '2026-02-01';
    pname text;
BEGIN
    WHILE d < stop LOOP
        pname := 'campaign_events_p' || to_char(d, 'YYYYMM');
        EXECUTE format(
            'CREATE TABLE %I PARTITION OF campaign_events_part FOR VALUES FROM (%L) TO (%L)',
            pname, d, (d + interval '1 month')::date
        );
        d := (d + interval '1 month')::date;
    END LOOP;
END
$$;

INSERT INTO campaign_events_part
SELECT event_id, campaign_id, customer_id, event_type, event_time, order_id, revenue
FROM campaign_events;

-- Local indexes (propagate to every partition).
CREATE INDEX ix_cep_type_time ON campaign_events_part (event_type, event_time);
CREATE INDEX ix_cep_campaign  ON campaign_events_part (campaign_id);

ANALYZE campaign_events_part;

SELECT count(*) AS partitioned_rows FROM campaign_events_part;
