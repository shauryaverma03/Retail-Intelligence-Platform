"""Dashboard metrics. Every number here is produced by a SQL query against the
synthetic database -- nothing is hardcoded or estimated.

Metric definitions (documented so reviewers can audit them):

  repeat_purchase_rate  = customers with >=2 completed orders
                          / customers with >=1 completed order
  retention_rate_90d    = of customers who bought in the 90-180d window,
                          the share who ALSO bought in the last 90d
  avg_order_value       = sum(net_amount) / count(order) over completed orders
  campaign_conv_rate    = convert events / sent events (campaign_events)
  at_risk_customers     = lifetime net in top 30% AND last completed order
                          90-365 days ago
"""
from __future__ import annotations

import time
from typing import Any

from ..db import fetch_all, fetch_one
from ..config import get_settings

_cache: dict[str, Any] = {"ts": 0.0, "data": None}


def _kpis() -> dict[str, Any]:
    row = fetch_one(
        """
        WITH per_customer AS (
            SELECT c.customer_id,
                   count(o.order_id) FILTER (WHERE o.status = 'completed') AS completed_orders,
                   max(o.order_date) FILTER (WHERE o.status = 'completed')  AS last_order,
                   sum(o.net_amount) FILTER (WHERE o.status = 'completed')  AS lifetime_net
            FROM customers c
            LEFT JOIN orders o ON o.customer_id = c.customer_id
            GROUP BY c.customer_id
        ),
        completed AS (
            SELECT net_amount, order_date FROM orders WHERE status = 'completed'
        )
        SELECT
            (SELECT count(*) FROM customers)                                         AS total_customers,
            count(*) FILTER (WHERE completed_orders >= 1)                             AS buyers,
            count(*) FILTER (WHERE completed_orders >= 2)                             AS repeat_buyers,
            round(100.0 * count(*) FILTER (WHERE completed_orders >= 2)
                  / NULLIF(count(*) FILTER (WHERE completed_orders >= 1), 0), 1)     AS repeat_purchase_rate_pct,
            count(*) FILTER (WHERE last_order >= now() - interval '90 days')          AS active_customers_90d,
            (SELECT count(*) FROM completed)                                         AS completed_orders,
            (SELECT round(avg(net_amount), 2) FROM completed)                        AS avg_order_value,
            (SELECT round(sum(net_amount), 2) FROM completed)                        AS total_net_revenue,
            (SELECT round(sum(net_amount), 2) FROM completed
                WHERE order_date >= now() - interval '30 days')                      AS net_revenue_30d,
            (SELECT round(sum(net_amount), 2) FROM completed
                WHERE order_date >= now() - interval '60 days'
                  AND order_date <  now() - interval '30 days')                      AS net_revenue_prev_30d
        FROM per_customer
        """
    )
    return row or {}


def _retention_90d() -> dict[str, Any]:
    row = fetch_one(
        """
        WITH prior AS (
            SELECT DISTINCT customer_id
            FROM orders
            WHERE status = 'completed'
              AND order_date >= now() - interval '180 days'
              AND order_date <  now() - interval '90 days'
        ),
        recent AS (
            SELECT DISTINCT customer_id
            FROM orders
            WHERE status = 'completed'
              AND order_date >= now() - interval '90 days'
        )
        SELECT (SELECT count(*) FROM prior)                                    AS prior_window_buyers,
               (SELECT count(*) FROM prior p WHERE EXISTS
                    (SELECT 1 FROM recent r WHERE r.customer_id = p.customer_id)) AS retained,
               round(100.0 * (SELECT count(*) FROM prior p WHERE EXISTS
                    (SELECT 1 FROM recent r WHERE r.customer_id = p.customer_id))
                     / NULLIF((SELECT count(*) FROM prior), 0), 1)             AS retention_rate_pct
        """
    )
    return row or {}


def _campaign_conversion() -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT count(*) FILTER (WHERE event_type = 'sent')     AS sent,
               count(*) FILTER (WHERE event_type = 'click')    AS clicks,
               count(*) FILTER (WHERE event_type = 'convert')  AS conversions,
               round(100.0 * count(*) FILTER (WHERE event_type = 'convert')
                     / NULLIF(count(*) FILTER (WHERE event_type = 'sent'), 0), 2) AS conversion_rate_pct,
               round(sum(revenue) FILTER (WHERE event_type = 'convert'), 2)       AS attributed_revenue
        FROM campaign_events
        """
    )
    return row or {}


def _at_risk() -> dict[str, Any]:
    row = fetch_one(
        """
        WITH cust AS (
            SELECT c.customer_id,
                   sum(o.net_amount)                      AS lifetime_net,
                   CURRENT_DATE - max(o.order_date)::date AS days_since_last_order
            FROM customers c
            JOIN orders o ON o.customer_id = c.customer_id AND o.status = 'completed'
            GROUP BY c.customer_id
        ),
        threshold AS (
            SELECT percentile_cont(0.70) WITHIN GROUP (ORDER BY lifetime_net) AS p70 FROM cust
        )
        SELECT count(*)                                            AS at_risk_customers,
               round(sum(cu.lifetime_net), 2)                      AS lifetime_net_at_risk,
               round(avg(cu.days_since_last_order))                AS avg_days_since_order
        FROM cust cu, threshold t
        WHERE cu.lifetime_net >= t.p70
          AND cu.days_since_last_order BETWEEN 90 AND 365
        """
    )
    return row or {}


def _revenue_trend() -> list[dict[str, Any]]:
    return fetch_all(
        """
        WITH months AS (
            SELECT date_trunc('month', CURRENT_DATE) - (n || ' months')::interval AS m
            FROM generate_series(0, 11) n
        ),
        rev AS (
            SELECT date_trunc('month', order_date) AS m,
                   sum(net_amount) AS net_revenue,
                   count(*) AS orders
            FROM orders
            WHERE status = 'completed'
              AND order_date >= date_trunc('month', CURRENT_DATE) - interval '12 months'
            GROUP BY 1
        )
        SELECT to_char(months.m, 'YYYY-MM')          AS month,
               COALESCE(rev.net_revenue, 0)::float   AS net_revenue,
               COALESCE(rev.orders, 0)               AS orders
        FROM months
        LEFT JOIN rev ON rev.m = months.m
        ORDER BY months.m
        """
    )


def _segment_performance() -> list[dict[str, Any]]:
    return fetch_all(
        """
        WITH base AS (
            SELECT c.customer_id,
                   CURRENT_DATE - max(o.order_date)::date AS recency_days,
                   count(*) AS frequency,
                   sum(o.net_amount) AS monetary
            FROM customers c
            JOIN orders o ON o.customer_id = c.customer_id AND o.status = 'completed'
            GROUP BY c.customer_id
        ),
        scored AS (
            SELECT customer_id, monetary, frequency,
                   6 - NTILE(5) OVER (ORDER BY recency_days) AS r,
                   NTILE(5) OVER (ORDER BY frequency)        AS f,
                   NTILE(5) OVER (ORDER BY monetary)         AS m
            FROM base
        ),
        seg AS (
            SELECT CASE
                     WHEN r >= 4 AND f >= 4 AND m >= 4 THEN 'Champions'
                     WHEN r >= 4 AND f >= 3            THEN 'Loyal'
                     WHEN r >= 4                       THEN 'New / Promising'
                     WHEN r = 3  AND f >= 3            THEN 'Potential Loyalist'
                     WHEN r <= 2 AND m >= 3            THEN 'At Risk / Hibernating'
                     ELSE 'Lost / Low value'
                   END AS segment,
                   monetary, frequency
            FROM scored
        )
        SELECT segment,
               count(*)                       AS customers,
               round(avg(frequency), 2)       AS avg_orders,
               round(avg(monetary), 2)        AS avg_lifetime_net,
               round(sum(monetary), 2)::float AS segment_lifetime_net
        FROM seg
        GROUP BY segment
        ORDER BY segment_lifetime_net DESC
        """
    )


def _data_freshness() -> dict[str, Any]:
    return fetch_one(
        """
        SELECT max(order_date)                            AS latest_order,
               (now() - max(order_date))::text            AS order_lag,
               round(extract(epoch FROM now() - max(order_date)) / 86400.0, 1) AS order_lag_days,
               (SELECT max(finished_at) FROM etl_runs
                  WHERE status = 'success')               AS last_successful_etl
        FROM orders
        """
    ) or {}


def dashboard_summary(refresh: bool = False) -> dict[str, Any]:
    ttl = get_settings().dashboard_cache_ttl_s
    now = time.time()
    if not refresh and _cache["data"] is not None and now - _cache["ts"] < ttl:
        return {**_cache["data"], "cached": True}

    started = time.perf_counter()
    kpis = _kpis()
    revenue_30d = kpis.get("net_revenue_30d") or 0
    revenue_prev_30d = kpis.get("net_revenue_prev_30d") or 0
    mom = None
    if revenue_prev_30d:
        mom = round((float(revenue_30d) / float(revenue_prev_30d) - 1) * 100, 1)

    data = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "build_ms": round((time.perf_counter() - started) * 1000, 1),
        "cached": False,
        "kpis": {
            **kpis,
            "revenue_mom_growth_pct": mom,
            **_retention_90d(),
        },
        "campaign_conversion": _campaign_conversion(),
        "at_risk": _at_risk(),
        "revenue_trend": _revenue_trend(),
        "segment_performance": _segment_performance(),
        "data_freshness": _data_freshness(),
        "note": "All figures computed live from synthetic data.",
    }
    _cache.update(ts=time.time(), data=data)
    return data
