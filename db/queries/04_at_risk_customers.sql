-- name: At-risk high-value customers
-- question: Which previously high-value customers are lapsing and how much revenue is at risk?
-- tags: customers, churn, retention, revenue-at-risk
-- techniques: percentile_cont, interval math, window percentile threshold, join back
-- "At risk" = lifetime net in the top 30% AND last completed order 90-365 days ago
-- (bought before, but has now gone quiet).
WITH cust AS (
    SELECT c.customer_id,
           c.full_name,
           c.acquisition_channel,
           count(*)                               AS lifetime_orders,
           sum(o.net_amount)                      AS lifetime_net,
           max(o.order_date)::date                AS last_order_date,
           CURRENT_DATE - max(o.order_date)::date AS days_since_last_order
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id AND o.status = 'completed'
    GROUP BY c.customer_id, c.full_name, c.acquisition_channel
),
threshold AS (
    SELECT percentile_cont(0.70) WITHIN GROUP (ORDER BY lifetime_net) AS p70_net
    FROM cust
)
SELECT cu.customer_id,
       cu.full_name,
       cu.acquisition_channel,
       cu.lifetime_orders,
       cu.lifetime_net::numeric(14,2),
       cu.last_order_date,
       cu.days_since_last_order
FROM cust cu, threshold t
WHERE cu.lifetime_net >= t.p70_net
  AND cu.days_since_last_order BETWEEN 90 AND 365
ORDER BY cu.lifetime_net DESC
LIMIT 200;
