-- name: Campaign funnel & ROI
-- question: How does each campaign perform from sent to converted, and what is its ROAS?
-- tags: campaigns, funnel, conversion, roas
-- techniques: conditional aggregation (FILTER), ratio-to-report, NULLIF guards
WITH funnel AS (
    SELECT ce.campaign_id,
           count(*) FILTER (WHERE event_type = 'sent')      AS sent,
           count(*) FILTER (WHERE event_type = 'delivered')  AS delivered,
           count(*) FILTER (WHERE event_type = 'open')       AS opens,
           count(*) FILTER (WHERE event_type = 'click')      AS clicks,
           count(*) FILTER (WHERE event_type = 'convert')    AS conversions,
           sum(revenue) FILTER (WHERE event_type = 'convert') AS revenue
    FROM campaign_events ce
    GROUP BY ce.campaign_id
)
SELECT c.campaign_id,
       c.campaign_name,
       c.channel,
       c.objective,
       f.sent,
       f.opens,
       f.clicks,
       f.conversions,
       round(100.0 * f.opens       / NULLIF(f.delivered, 0), 2) AS open_rate_pct,
       round(100.0 * f.clicks      / NULLIF(f.opens, 0), 2)     AS click_through_pct,
       round(100.0 * f.conversions / NULLIF(f.sent, 0), 2)      AS conversion_rate_pct,
       f.revenue::numeric(14,2)                                 AS attributed_revenue,
       c.budget,
       round(f.revenue / NULLIF(c.budget, 0), 2)                AS roas
FROM campaigns c
JOIN funnel f ON f.campaign_id = c.campaign_id
ORDER BY roas DESC NULLS LAST;
