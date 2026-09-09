-- name: RFM segmentation
-- question: How do customers break down by RFM segment, and what is each segment worth?
-- tags: customers, rfm, segmentation
-- techniques: NTILE window functions, CASE segment mapping, CTE chaining
-- Recency / Frequency / Monetary scored 1-5 with NTILE over completed orders,
-- then mapped to named segments and rolled up.
WITH base AS (
    SELECT c.customer_id,
           CURRENT_DATE - max(o.order_date)::date       AS recency_days,
           count(*)                                     AS frequency,
           sum(o.net_amount)                            AS monetary
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id AND o.status = 'completed'
    GROUP BY c.customer_id
),
scored AS (
    SELECT b.*,
           6 - NTILE(5) OVER (ORDER BY recency_days)              AS r_score,  -- lower recency = better
           NTILE(5) OVER (ORDER BY frequency)                     AS f_score,
           NTILE(5) OVER (ORDER BY monetary)                      AS m_score
    FROM base b
),
segmented AS (
    SELECT s.*,
           CASE
               WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
               WHEN r_score >= 4 AND f_score >= 3                  THEN 'Loyal'
               WHEN r_score >= 4 AND f_score <= 2                  THEN 'New / Promising'
               WHEN r_score = 3  AND f_score >= 3                  THEN 'Potential Loyalist'
               WHEN r_score <= 2 AND f_score >= 4 AND m_score >= 4 THEN 'At Risk (high value)'
               WHEN r_score <= 2 AND f_score >= 3                  THEN 'At Risk'
               WHEN r_score <= 2 AND f_score <= 2 AND m_score >= 3 THEN 'Hibernating (was valuable)'
               ELSE 'Lost / Low value'
           END AS segment
    FROM scored s
)
SELECT segment,
       count(*)                                          AS customers,
       round(avg(recency_days))                          AS avg_recency_days,
       round(avg(frequency), 2)                          AS avg_orders,
       round(avg(monetary), 2)                           AS avg_lifetime_net,
       round(sum(monetary), 2)                           AS segment_lifetime_net,
       round(100.0 * sum(monetary) / sum(sum(monetary)) OVER (), 1) AS pct_of_total_net
FROM segmented
GROUP BY segment
ORDER BY segment_lifetime_net DESC;
