-- name: Repeat purchase rate by acquisition channel
-- question: Which acquisition channels bring customers who buy more than once?
-- tags: customers, retention, acquisition, repeat-rate
-- techniques: per-customer aggregation, boolean aggregation, grouping rollup
WITH per_customer AS (
    SELECT c.customer_id,
           c.acquisition_channel,
           count(o.order_id) FILTER (WHERE o.status = 'completed') AS completed_orders,
           sum(o.net_amount) FILTER (WHERE o.status = 'completed') AS lifetime_net
    FROM customers c
    LEFT JOIN orders o ON o.customer_id = c.customer_id
    GROUP BY c.customer_id, c.acquisition_channel
)
SELECT acquisition_channel,
       count(*)                                                          AS customers,
       count(*) FILTER (WHERE completed_orders >= 1)                      AS buyers,
       count(*) FILTER (WHERE completed_orders >= 2)                      AS repeat_buyers,
       round(100.0 * count(*) FILTER (WHERE completed_orders >= 2)
                     / NULLIF(count(*) FILTER (WHERE completed_orders >= 1), 0), 1) AS repeat_rate_pct,
       round(avg(lifetime_net) FILTER (WHERE completed_orders >= 1), 2)   AS avg_ltv
FROM per_customer
GROUP BY acquisition_channel
ORDER BY repeat_rate_pct DESC;
