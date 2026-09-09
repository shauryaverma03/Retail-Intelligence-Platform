"""Data-quality checks. Each check is a single SQL query returning real counts.

A check has: id, title, category, severity, a `metric` (the number that matters),
`detail` rows (a small sample / breakdown), and a pass/fail `status` decided by a
threshold. Nothing is faked -- if the synthetic data is clean, the check passes.
"""
from __future__ import annotations

import time
from typing import Any

from ..db import fetch_all, fetch_one


def _check(cur_id, title, category, severity, sql, threshold, status_key="metric",
           detail_sql=None):
    row = fetch_one(sql) or {}
    metric = row.get(status_key)
    metric = 0 if metric is None else metric
    status = "pass" if metric <= threshold else "fail"
    detail = fetch_all(detail_sql) if detail_sql else [row]
    return {
        "id": cur_id,
        "title": title,
        "category": category,
        "severity": severity,
        "metric": metric,
        "threshold": threshold,
        "status": status,
        "detail": detail,
    }


def run_all_checks() -> dict[str, Any]:
    started = time.perf_counter()
    checks: list[dict[str, Any]] = []

    # 1. Missing values -----------------------------------------------------
    checks.append(_check(
        "missing_customer_email", "Customers missing email", "completeness", "medium",
        """
        SELECT count(*) AS metric,
               round(100.0 * count(*) / (SELECT count(*) FROM customers), 2) AS pct_of_customers
        FROM customers WHERE email IS NULL OR email = ''
        """,
        threshold=0,
    ))
    checks.append(_check(
        "missing_customer_birth_year", "Customers missing birth year", "completeness", "low",
        """
        SELECT count(*) AS metric,
               round(100.0 * count(*) / (SELECT count(*) FROM customers), 2) AS pct_of_customers
        FROM customers WHERE birth_year IS NULL
        """,
        threshold=0,
    ))
    checks.append(_check(
        "orders_zero_amount", "Completed orders with zero net amount", "validity", "high",
        """
        SELECT count(*) AS metric FROM orders
        WHERE status = 'completed' AND net_amount <= 0
        """,
        threshold=0,
    ))

    # 2. Duplicate IDs / natural keys ------------------------------------
    checks.append(_check(
        "duplicate_customer_email", "Duplicate customer emails", "uniqueness", "high",
        """
        SELECT COALESCE(sum(c - 1), 0) AS metric FROM (
            SELECT count(*) c FROM customers
            WHERE email IS NOT NULL GROUP BY lower(email) HAVING count(*) > 1
        ) d
        """,
        threshold=0,
        detail_sql="""
            SELECT lower(email) AS email, count(*) AS rows
            FROM customers WHERE email IS NOT NULL
            GROUP BY lower(email) HAVING count(*) > 1
            ORDER BY count(*) DESC LIMIT 20
        """,
    ))
    checks.append(_check(
        "duplicate_sku", "Duplicate product SKUs", "uniqueness", "high",
        """
        SELECT COALESCE(sum(c - 1), 0) AS metric FROM (
            SELECT count(*) c FROM products GROUP BY sku HAVING count(*) > 1
        ) d
        """,
        threshold=0,
    ))

    # 3. Invalid dates ------------------------------------------------------
    checks.append(_check(
        "order_before_signup", "Orders dated before customer signup", "validity", "high",
        """
        SELECT count(*) AS metric
        FROM orders o JOIN customers c ON c.customer_id = o.customer_id
        WHERE o.order_date::date < c.signup_date
        """,
        threshold=0,
        detail_sql="""
            SELECT o.order_id, o.customer_id, o.order_date::date AS order_date, c.signup_date
            FROM orders o JOIN customers c ON c.customer_id = o.customer_id
            WHERE o.order_date::date < c.signup_date
            ORDER BY o.order_id LIMIT 20
        """,
    ))
    checks.append(_check(
        "future_order_date", "Orders dated in the future", "validity", "high",
        "SELECT count(*) AS metric FROM orders WHERE order_date > now()",
        threshold=0,
    ))
    checks.append(_check(
        "campaign_end_before_start", "Campaigns ending before they start", "validity", "medium",
        "SELECT count(*) AS metric FROM campaigns WHERE end_date < start_date",
        threshold=0,
    ))

    # 4. Duplicate orders (double-submit) ---------------------------------
    checks.append(_check(
        "duplicate_orders", "Likely duplicate orders (same customer, timestamp, amount)",
        "uniqueness", "high",
        """
        SELECT COALESCE(sum(c - 1), 0) AS metric FROM (
            SELECT count(*) c
            FROM orders
            GROUP BY customer_id, order_date, net_amount
            HAVING count(*) > 1
        ) d
        """,
        threshold=0,
        detail_sql="""
            SELECT customer_id, order_date, net_amount, count(*) AS duplicate_rows,
                   array_agg(order_id ORDER BY order_id) AS order_ids
            FROM orders
            GROUP BY customer_id, order_date, net_amount
            HAVING count(*) > 1
            ORDER BY count(*) DESC LIMIT 20
        """,
    ))

    # 5. Referential integrity -------------------------------------------
    checks.append(_check(
        "orphan_order_items", "Order items pointing at a missing order", "integrity", "high",
        """
        SELECT count(*) AS metric FROM order_items oi
        LEFT JOIN orders o ON o.order_id = oi.order_id
        WHERE o.order_id IS NULL
        """,
        threshold=0,
    ))

    # 6. Data freshness -------------------------------------------------
    freshness = fetch_one(
        """
        SELECT max(order_date)                        AS latest_order,
               round(extract(epoch FROM now() - max(order_date)) / 3600.0, 1) AS hours_since_latest_order,
               (SELECT max(event_time) FROM campaign_events) AS latest_event
        FROM orders
        """
    ) or {}
    fresh_hours = float(freshness.get("hours_since_latest_order") or 0)
    checks.append({
        "id": "data_freshness",
        "title": "Data freshness (latest order recency)",
        "category": "timeliness",
        "severity": "medium",
        "metric": fresh_hours,
        "threshold": 720,  # 30 days -- synthetic data has a fixed 'now'
        "status": "pass" if fresh_hours <= 720 else "warn",
        "detail": [freshness],
    })

    # 7. Pipeline status ------------------------------------------------
    pipeline = fetch_all(
        """
        SELECT DISTINCT ON (pipeline)
               pipeline, status, started_at, finished_at, rows_loaded, message
        FROM etl_runs
        ORDER BY pipeline, started_at DESC
        """
    )
    failed = [p for p in pipeline if p["status"] != "success"]
    checks.append({
        "id": "pipeline_status",
        "title": "ETL pipeline status (latest run per pipeline)",
        "category": "pipeline",
        "severity": "high",
        "metric": len(failed),
        "threshold": 0,
        "status": "pass" if not failed else "fail",
        "detail": pipeline,
    })

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed_n = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warn")
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "summary": {
            "total": len(checks),
            "passed": passed,
            "failed": failed_n,
            "warnings": warned,
            "health_score": round(100.0 * passed / len(checks), 1),
        },
        "checks": checks,
        "note": (
            "The synthetic seed deliberately injects a small number of duplicate "
            "customer emails and duplicate orders so these checks have something "
            "to catch."
        ),
    }
