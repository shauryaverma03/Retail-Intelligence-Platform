-- =============================================================================
-- XenoPulse :: Synthetic data generator  (pure SQL, set-based, deterministic)
-- =============================================================================
-- Every row produced here is SYNTHETIC and labelled is_synthetic = TRUE.
--
-- Volume is controlled by the generate_series bounds below. Defaults produce a
-- dataset large enough that indexing / join order / filter placement produce
-- measurable (10x-500x) differences in the Query Performance Lab:
--
--     customers        ~60,000
--     products           2,000
--     campaigns             48
--     orders          ~210,000
--     order_items     ~630,000
--     campaign_events ~2,300,000
--     etl_runs              14
--
-- (row counts vary slightly run-to-run within the random distributions).
-- Runtime: ~20-45s on a laptop. Re-runnable: truncates first, fixed seed.
-- =============================================================================

\timing on
SET client_min_messages = warning;

TRUNCATE campaign_events, order_items, orders, campaigns, products, customers, etl_runs
    RESTART IDENTITY CASCADE;

-- Deterministic pseudo-randomness for reproducible benchmarks.
SELECT setseed(0.42);

-- -----------------------------------------------------------------------------
-- 1. customers
-- -----------------------------------------------------------------------------
-- One random city index per row (drawn in the inner SELECT list so random() is
-- re-evaluated per row); region is derived from the city so the two agree.
INSERT INTO customers (full_name, email, city, region, country, acquisition_channel, signup_date, birth_year)
SELECT
    s.full_name,
    s.email,
    s.city,
    CASE
        WHEN s.city IN ('Mumbai','Pune','Ahmedabad')     THEN 'West'
        WHEN s.city IN ('Delhi','Jaipur','Lucknow')      THEN 'North'
        WHEN s.city IN ('Bengaluru','Chennai','Hyderabad') THEN 'South'
        ELSE 'East'
    END AS region,
    'IN',
    s.acquisition_channel,
    s.signup_date,
    s.birth_year
FROM (
    SELECT
        'Synthetic Customer ' || g AS full_name,
        CASE
            WHEN random() < 0.04  THEN NULL
            WHEN random() < 0.002 THEN 'dupe.customer@synthetic.example'
            ELSE 'customer' || g || '@synthetic.example'
        END AS email,
        (ARRAY['Mumbai','Pune','Ahmedabad','Delhi','Jaipur','Lucknow',
               'Bengaluru','Chennai','Hyderabad','Kolkata','Patna','Guwahati']
        )[(1 + floor(random() * 12))::int] AS city,
        (ARRAY['organic','paid_search','social','referral','email']
        )[(1 + floor(random() * 5))::int] AS acquisition_channel,
        DATE '2022-01-01' + (random() * 1200)::int AS signup_date,
        CASE WHEN random() < 0.12 THEN NULL ELSE 1955 + floor(random() * 52)::int END AS birth_year
    FROM generate_series(1, 60000) AS g
) AS s;

-- -----------------------------------------------------------------------------
-- 2. products
-- -----------------------------------------------------------------------------
INSERT INTO products (sku, product_name, category, subcategory, unit_price, unit_cost, is_active, launch_date)
SELECT
    'SKU-' || lpad(s.g::text, 6, '0'),
    cat.category || ' Item ' || s.g,
    cat.category,
    cat.subcategory,
    s.price,
    round((s.price * (0.45 + random() * 0.3))::numeric, 2),          -- cost = 45-75% of price
    (random() < 0.9),
    DATE '2021-06-01' + (random() * 1400)::int
FROM (
    SELECT g,
           (1 + floor(random() * 10))::int              AS pick,
           round((80 + random() * 6000)::numeric, 2)    AS price
    FROM generate_series(1, 2000) AS g
) AS s
CROSS JOIN LATERAL (
    SELECT (ARRAY['Apparel','Apparel','Beauty','Beauty','Home','Home',
                  'Electronics','Electronics','Grocery','Grocery'])[s.pick]  AS category,
           (ARRAY['Tops','Footwear','Skincare','Fragrance','Kitchen','Decor',
                  'Audio','Wearables','Snacks','Beverages'])[s.pick]         AS subcategory
) AS cat;

-- -----------------------------------------------------------------------------
-- 3. campaigns  (48 campaigns spread across 2022-2025)
-- -----------------------------------------------------------------------------
INSERT INTO campaigns (campaign_name, channel, objective, start_date, end_date, budget)
SELECT
    d.objective || ' - ' || d.channel || ' #' || g,
    d.channel,
    d.objective,
    d.start_d,
    d.start_d + (7 + floor(random() * 35))::int,
    round((50000 + random() * 900000)::numeric, 2)
FROM generate_series(1, 48) AS g
CROSS JOIN LATERAL (
    -- correlated on g, so random() is re-evaluated for every campaign
    SELECT
        DATE '2022-01-15' + (g * 28 + floor(random() * 14))::int              AS start_d,
        (ARRAY['email','sms','push','social','paid_search'])[(1 + floor(random() * 5))::int]  AS channel,
        (ARRAY['acquisition','retention','winback','upsell'])[(1 + floor(random() * 4))::int] AS objective
) AS d;

-- -----------------------------------------------------------------------------
-- 4. orders
-- -----------------------------------------------------------------------------
-- Per-customer order count follows a heavy-tailed distribution:
--   n = floor(-ln(random) * 4.0)   -> ~22% of customers get 0 (never purchased),
--   most get 1-6, a long tail buys 20-40 times. Capped at 40.
-- Each customer gets a "tenure" (days signup..today) and a random "lapse" of up
-- to 70% of it; orders are spread only over the un-lapsed part, so some
-- customers are still active and some clearly went quiet (recency/churn work).
INSERT INTO orders (customer_id, order_date, status, channel, ship_region,
                    discount_amount, shipping_fee)
SELECT
    c.customer_id,
    (c.signup_date
        + make_interval(days => floor(random() * GREATEST(1, w.active_days))::int)
        + make_interval(secs => floor(random() * 86400)))::timestamptz,
    (ARRAY['completed','completed','completed','completed','completed','completed',
           'completed','completed','returned','cancelled','pending'])[(1 + floor(random() * 11))::int],
    (ARRAY['web','web','mobile_app','mobile_app','mobile_app','store','marketplace'])[(1 + floor(random() * 7))::int],
    c.region,
    CASE WHEN random() < 0.35 THEN round((random() * 900)::numeric, 2) ELSE 0 END,
    CASE WHEN random() < 0.55 THEN round((49 + random() * 150)::numeric, 2) ELSE 0 END
FROM customers c
CROSS JOIN LATERAL (SELECT GREATEST(1, (CURRENT_DATE - c.signup_date)) AS tenure_days) AS t
CROSS JOIN LATERAL (SELECT (t.tenure_days * (1.0 - random() * 0.7))::int AS active_days) AS w
CROSS JOIN LATERAL
    generate_series(1, LEAST(40, floor(-ln(random() * (1 - 1e-9) + 1e-9) * 4.0)::int)) AS ord;

-- -----------------------------------------------------------------------------
-- 5. order_items  (1-6 lines per order, product picked by contiguous id)
-- -----------------------------------------------------------------------------
INSERT INTO order_items (order_id, product_id, quantity, unit_price, line_total)
SELECT
    o.order_id,
    li.pid,
    li.qty,
    p.unit_price,
    round((li.qty * p.unit_price)::numeric, 2)
FROM orders o
CROSS JOIN LATERAL generate_series(1, 1 + floor(random() * 5)::int) AS line_no
CROSS JOIN LATERAL (
    -- correlated on line_no -> fresh qty/product for every line
    SELECT
        (1 + floor(random() * 4))::int    AS qty,
        (1 + floor(random() * 2000))::int AS pid,
        line_no                            AS _ln
) AS li
JOIN products p ON p.product_id = li.pid;

-- roll line items up into stored order totals
UPDATE orders o
SET gross_amount = s.gross,
    net_amount   = GREATEST(0, s.gross - o.discount_amount) + o.shipping_fee
FROM (
    SELECT order_id, sum(line_total) AS gross
    FROM order_items
    GROUP BY order_id
) s
WHERE s.order_id = o.order_id;

-- -----------------------------------------------------------------------------
-- 5b. attribute ~22% of orders to a campaign whose window contains the order
-- -----------------------------------------------------------------------------
UPDATE orders o
SET campaign_id = c.campaign_id
FROM campaigns c
WHERE o.order_date::date BETWEEN c.start_date AND c.end_date
  AND o.campaign_id IS NULL
  AND random() < 0.22;

-- -----------------------------------------------------------------------------
-- 5c. a deliberate cluster of DUPLICATE orders for the Data Quality demo
--     (same customer, same timestamp, same amount -- classic double-submit bug)
-- -----------------------------------------------------------------------------
INSERT INTO orders (customer_id, order_date, status, channel, ship_region,
                    discount_amount, shipping_fee, gross_amount, net_amount, campaign_id)
SELECT customer_id, order_date, status, channel, ship_region,
       discount_amount, shipping_fee, gross_amount, net_amount, campaign_id
FROM orders
WHERE status = 'completed'
ORDER BY order_id
LIMIT 120;

-- -----------------------------------------------------------------------------
-- 6. campaign_events  (funnel: sent -> delivered -> open -> click -> convert)
-- -----------------------------------------------------------------------------
-- 6a. sent: ~32% of customers targeted per campaign (re-rolled per campaign)
INSERT INTO campaign_events (campaign_id, customer_id, event_type, event_time, revenue)
SELECT
    c.campaign_id,
    cu.customer_id,
    'sent',
    (c.start_date
        + make_interval(days => floor(random() * GREATEST(1, c.end_date - c.start_date))::int)
        + make_interval(secs => floor(random() * 86400)))::timestamptz,
    0
FROM campaigns c
JOIN LATERAL (
    SELECT customer_id FROM customers WHERE random() < 0.32
) cu ON TRUE;

-- 6b. delivered: 96% of sent
INSERT INTO campaign_events (campaign_id, customer_id, event_type, event_time, revenue)
SELECT campaign_id, customer_id, 'delivered', event_time + make_interval(secs => 30 + floor(random() * 120)), 0
FROM campaign_events
WHERE event_type = 'sent' AND random() < 0.96;

-- 6c. open: 42% of delivered
INSERT INTO campaign_events (campaign_id, customer_id, event_type, event_time, revenue)
SELECT campaign_id, customer_id, 'open', event_time + make_interval(secs => 300 + floor(random() * 43200)), 0
FROM campaign_events
WHERE event_type = 'delivered' AND random() < 0.42;

-- 6d. click: 28% of open
INSERT INTO campaign_events (campaign_id, customer_id, event_type, event_time, revenue)
SELECT campaign_id, customer_id, 'click', event_time + make_interval(secs => 60 + floor(random() * 7200)), 0
FROM campaign_events
WHERE event_type = 'open' AND random() < 0.28;

-- 6e. convert: 19% of click, carries synthetic revenue
INSERT INTO campaign_events (campaign_id, customer_id, event_type, event_time, revenue)
SELECT campaign_id, customer_id, 'convert',
       event_time + make_interval(secs => 120 + floor(random() * 10800)),
       round((600 + random() * 5200)::numeric, 2)
FROM campaign_events
WHERE event_type = 'click' AND random() < 0.19;

-- 6f. unsubscribe: 0.8% of delivered
INSERT INTO campaign_events (campaign_id, customer_id, event_type, event_time, revenue)
SELECT campaign_id, customer_id, 'unsubscribe', event_time + make_interval(secs => 600 + floor(random() * 86400)), 0
FROM campaign_events
WHERE event_type = 'delivered' AND random() < 0.008;

-- link convert events to a plausible completed order by the same customer
UPDATE campaign_events ce
SET order_id = o.order_id
FROM LATERAL (
    SELECT o.order_id
    FROM orders o
    WHERE o.customer_id = ce.customer_id
      AND o.status = 'completed'
      AND o.order_date BETWEEN ce.event_time - interval '3 days' AND ce.event_time + interval '3 days'
    ORDER BY o.order_date
    LIMIT 1
) o
WHERE ce.event_type = 'convert' AND ce.order_id IS NULL;

-- -----------------------------------------------------------------------------
-- 7. etl_runs  (synthetic pipeline history; last run is fresh + successful)
-- -----------------------------------------------------------------------------
INSERT INTO etl_runs (pipeline, status, started_at, finished_at, rows_loaded, message)
SELECT
    (ARRAY['orders_ingest','customers_ingest','campaign_events_ingest'])[1 + (g % 3)::int],
    CASE WHEN g = 2 THEN 'failed' ELSE 'success' END,
    now() - make_interval(hours => g * 6),
    now() - make_interval(hours => g * 6) + interval '11 minutes',
    CASE WHEN g = 2 THEN NULL ELSE (5000 + floor(random() * 40000))::bigint END,
    CASE WHEN g = 2 THEN 'source file arrived truncated; retried next window' ELSE 'ok' END
FROM generate_series(1, 14) AS g;

-- -----------------------------------------------------------------------------
-- Finalise: keep the planner honest.
-- -----------------------------------------------------------------------------
ANALYZE customers;
ANALYZE products;
ANALYZE campaigns;
ANALYZE orders;
ANALYZE order_items;
ANALYZE campaign_events;
ANALYZE etl_runs;

-- Quick sanity readout
SELECT 'customers'       AS table_name, count(*) FROM customers
UNION ALL SELECT 'products',        count(*) FROM products
UNION ALL SELECT 'campaigns',       count(*) FROM campaigns
UNION ALL SELECT 'orders',          count(*) FROM orders
UNION ALL SELECT 'order_items',     count(*) FROM order_items
UNION ALL SELECT 'campaign_events', count(*) FROM campaign_events
UNION ALL SELECT 'etl_runs',        count(*) FROM etl_runs
ORDER BY table_name;
