-- name: New vs returning revenue split by month
-- question: Each month, how much revenue comes from a customer's first order vs later orders?
-- tags: revenue, retention, acquisition
-- techniques: window row_number per customer ordered by date, CASE bucket, pivot
WITH ranked_orders AS (
    SELECT o.order_id,
           o.customer_id,
           o.order_date,
           o.net_amount,
           row_number() OVER (PARTITION BY o.customer_id ORDER BY o.order_date, o.order_id) AS order_seq
    FROM orders o
    WHERE o.status = 'completed'
)
SELECT to_char(date_trunc('month', order_date), 'YYYY-MM')                 AS month,
       round(sum(net_amount) FILTER (WHERE order_seq = 1), 2)              AS new_customer_revenue,
       round(sum(net_amount) FILTER (WHERE order_seq > 1), 2)             AS returning_customer_revenue,
       round(100.0 * sum(net_amount) FILTER (WHERE order_seq > 1)
                     / NULLIF(sum(net_amount), 0), 1)                      AS returning_share_pct
FROM ranked_orders
WHERE order_date >= date_trunc('month', CURRENT_DATE) - interval '18 months'
GROUP BY 1
ORDER BY 1;
