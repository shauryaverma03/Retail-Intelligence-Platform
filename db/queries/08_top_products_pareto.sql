-- name: Product revenue Pareto (80/20)
-- question: What share of products drives 80% of revenue?
-- tags: products, pareto, concentration
-- techniques: window running total, ratio-to-report, cumulative distribution
WITH product_rev AS (
    SELECT p.product_id,
           p.product_name,
           p.category,
           sum(oi.line_total) AS revenue,
           sum(oi.quantity)   AS units
    FROM order_items oi
    JOIN orders o   ON o.order_id = oi.order_id AND o.status = 'completed'
    JOIN products p ON p.product_id = oi.product_id
    GROUP BY p.product_id, p.product_name, p.category
),
ranked AS (
    SELECT pr.*,
           sum(revenue) OVER (ORDER BY revenue DESC
                              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_revenue,
           sum(revenue) OVER ()                                                 AS total_revenue,
           row_number() OVER (ORDER BY revenue DESC)                            AS rev_rank
    FROM product_rev pr
)
SELECT rev_rank,
       product_name,
       category,
       revenue::numeric(14,2),
       units,
       round(100.0 * running_revenue / total_revenue, 2) AS cumulative_revenue_pct
FROM ranked
WHERE rev_rank <= 50
ORDER BY rev_rank;
