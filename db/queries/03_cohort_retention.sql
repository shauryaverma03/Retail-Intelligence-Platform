-- name: Monthly cohort retention
-- question: For each signup-month cohort, what share of customers are still ordering N months later?
-- tags: customers, cohort, retention
-- techniques: cohort indexing, month arithmetic, conditional aggregation, pivot
-- Cohort = calendar month of first completed order. Cell = % of the cohort with
-- >=1 completed order in cohort_month + k.
WITH first_order AS (
    SELECT customer_id,
           date_trunc('month', min(order_date)) AS cohort_month
    FROM orders
    WHERE status = 'completed'
    GROUP BY customer_id
),
activity AS (
    SELECT DISTINCT f.customer_id,
           f.cohort_month,
           (date_part('year',  age(date_trunc('month', o.order_date), f.cohort_month)) * 12
          + date_part('month', age(date_trunc('month', o.order_date), f.cohort_month)))::int AS month_offset
    FROM first_order f
    JOIN orders o ON o.customer_id = f.customer_id AND o.status = 'completed'
),
sizes AS (
    SELECT cohort_month, count(*) AS cohort_size
    FROM first_order
    GROUP BY cohort_month
)
SELECT to_char(s.cohort_month, 'YYYY-MM')                              AS cohort,
       s.cohort_size,
       round(100.0 * count(*) FILTER (WHERE a.month_offset = 1) / s.cohort_size, 1) AS m1_pct,
       round(100.0 * count(*) FILTER (WHERE a.month_offset = 2) / s.cohort_size, 1) AS m2_pct,
       round(100.0 * count(*) FILTER (WHERE a.month_offset = 3) / s.cohort_size, 1) AS m3_pct,
       round(100.0 * count(*) FILTER (WHERE a.month_offset = 6) / s.cohort_size, 1) AS m6_pct,
       round(100.0 * count(*) FILTER (WHERE a.month_offset = 12) / s.cohort_size, 1) AS m12_pct
FROM sizes s
JOIN activity a ON a.cohort_month = s.cohort_month
WHERE s.cohort_month >= date_trunc('month', CURRENT_DATE) - interval '24 months'
GROUP BY s.cohort_month, s.cohort_size
ORDER BY s.cohort_month;
