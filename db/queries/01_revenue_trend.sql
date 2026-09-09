-- name: Monthly revenue trend (last 18 months)
-- question: How has monthly net revenue trended over the last 18 months?
-- tags: revenue, trend, time-series
-- techniques: date_trunc, generate_series gap-fill, LEFT JOIN, window MoM growth
-- Gap-fills months with zero orders so the chart has no holes, and adds
-- month-over-month growth via LAG().
WITH months AS (
    SELECT date_trunc('month', CURRENT_DATE) - (n || ' months')::interval AS month_start
    FROM generate_series(0, 17) AS n
),
monthly AS (
    SELECT date_trunc('month', o.order_date) AS month_start,
           sum(o.net_amount)                 AS net_revenue,
           count(*)                          AS orders,
           count(DISTINCT o.customer_id)     AS buyers
    FROM orders o
    WHERE o.status = 'completed'
      AND o.order_date >= date_trunc('month', CURRENT_DATE) - interval '18 months'
    GROUP BY 1
)
SELECT to_char(m.month_start, 'YYYY-MM')                       AS month,
       COALESCE(x.net_revenue, 0)::numeric(14,2)               AS net_revenue,
       COALESCE(x.orders, 0)                                    AS orders,
       COALESCE(x.buyers, 0)                                    AS buyers,
       round(
           COALESCE(x.net_revenue, 0)
           / NULLIF(LAG(x.net_revenue) OVER (ORDER BY m.month_start), 0) - 1
       , 4)                                                     AS mom_growth
FROM months m
LEFT JOIN monthly x ON x.month_start = m.month_start
ORDER BY m.month_start;
