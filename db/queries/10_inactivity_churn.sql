-- name: Churn / inactivity buckets
-- question: How are active buyers distributed across recency buckets, and what revenue sits in each?
-- tags: customers, churn, inactivity
-- techniques: width_bucket-style CASE, aggregation, share-of-total window
WITH last_order AS (
    SELECT o.customer_id,
           max(o.order_date)::date                AS last_order_date,
           CURRENT_DATE - max(o.order_date)::date AS days_inactive,
           sum(o.net_amount)                      AS lifetime_net,
           count(*)                               AS lifetime_orders
    FROM orders o
    WHERE o.status = 'completed'
    GROUP BY o.customer_id
),
bucketed AS (
    SELECT lo.*,
           CASE
               WHEN days_inactive <= 30  THEN '0-30d  (active)'
               WHEN days_inactive <= 90  THEN '31-90d (cooling)'
               WHEN days_inactive <= 180 THEN '91-180d (at risk)'
               WHEN days_inactive <= 365 THEN '181-365d (lapsed)'
               ELSE '365d+ (churned)'
           END AS recency_bucket
    FROM last_order lo
)
SELECT recency_bucket,
       count(*)                                                     AS customers,
       round(avg(lifetime_orders), 1)                               AS avg_orders,
       round(sum(lifetime_net), 2)                                  AS lifetime_net_in_bucket,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1)           AS pct_customers,
       round(100.0 * sum(lifetime_net) / sum(sum(lifetime_net)) OVER (), 1) AS pct_lifetime_net
FROM bucketed
GROUP BY recency_bucket
ORDER BY min(days_inactive);
