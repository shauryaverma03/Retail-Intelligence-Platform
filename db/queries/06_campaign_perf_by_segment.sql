-- name: Campaign performance by RFM segment
-- question: Which customer segments convert best on campaigns, and where is spend wasted?
-- tags: campaigns, segmentation, conversion
-- techniques: reusable RFM CTE, join events to segment, conditional aggregation
WITH base AS (
    SELECT c.customer_id,
           CURRENT_DATE - max(o.order_date)::date AS recency_days,
           count(*)                               AS frequency,
           sum(o.net_amount)                      AS monetary
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id AND o.status = 'completed'
    GROUP BY c.customer_id
),
scored AS (
    SELECT customer_id,
           6 - NTILE(5) OVER (ORDER BY recency_days) AS r_score,
           NTILE(5) OVER (ORDER BY frequency)        AS f_score,
           NTILE(5) OVER (ORDER BY monetary)         AS m_score
    FROM base
),
seg AS (
    SELECT customer_id,
           CASE
               WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
               WHEN r_score >= 4 AND f_score >= 3                  THEN 'Loyal'
               WHEN r_score >= 4                                   THEN 'New / Promising'
               WHEN r_score <= 2 AND m_score >= 3                  THEN 'At Risk / Hibernating'
               ELSE 'Other'
           END AS segment
    FROM scored
)
SELECT COALESCE(s.segment, 'Never purchased')                      AS segment,
       count(*) FILTER (WHERE ce.event_type = 'sent')              AS sent,
       count(*) FILTER (WHERE ce.event_type = 'click')             AS clicks,
       count(*) FILTER (WHERE ce.event_type = 'convert')           AS conversions,
       round(100.0 * count(*) FILTER (WHERE ce.event_type = 'convert')
                     / NULLIF(count(*) FILTER (WHERE ce.event_type = 'sent'), 0), 2) AS conv_rate_pct,
       round(sum(ce.revenue) FILTER (WHERE ce.event_type = 'convert'), 2)            AS revenue,
       round(sum(ce.revenue) FILTER (WHERE ce.event_type = 'convert')
                     / NULLIF(count(*) FILTER (WHERE ce.event_type = 'sent'), 0), 2) AS revenue_per_send
FROM campaign_events ce
LEFT JOIN seg s ON s.customer_id = ce.customer_id
GROUP BY COALESCE(s.segment, 'Never purchased')
ORDER BY revenue DESC NULLS LAST;
