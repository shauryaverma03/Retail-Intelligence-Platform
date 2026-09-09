"""Business recommendations.

Each item is generated from a live SQL result. The `evidence` string only ever
contains numbers that came back from the database in this request. The
`expected_impact` is expressed as an explicit, checkable arithmetic statement
("if X of the Y at-risk customers reactivate at the current AOV ...") rather than
a bare claim.
"""
from __future__ import annotations

import time
from typing import Any

from ..db import fetch_all, fetch_one


def _fmt_money(v: Any) -> str:
    try:
        return f"₹{float(v):,.0f}"
    except (TypeError, ValueError):
        return str(v)


def _at_risk_reactivation() -> dict[str, Any]:
    row = fetch_one(
        """
        WITH cust AS (
            SELECT c.customer_id, sum(o.net_amount) AS lifetime_net,
                   count(*) AS orders,
                   CURRENT_DATE - max(o.order_date)::date AS days_since
            FROM customers c
            JOIN orders o ON o.customer_id = c.customer_id AND o.status = 'completed'
            GROUP BY c.customer_id
        ),
        t AS (SELECT percentile_cont(0.70) WITHIN GROUP (ORDER BY lifetime_net) p70 FROM cust),
        aov AS (SELECT avg(net_amount) a FROM orders WHERE status = 'completed')
        SELECT count(*)                              AS at_risk_customers,
               round(sum(cu.lifetime_net), 2)        AS lifetime_net_at_risk,
               round(avg(cu.lifetime_net), 2)        AS avg_lifetime_net,
               round((SELECT a FROM aov), 2)         AS current_aov,
               round(avg(cu.days_since))             AS avg_days_since_order
        FROM cust cu, t
        WHERE cu.lifetime_net >= t.p70 AND cu.days_since BETWEEN 90 AND 365
        """
    ) or {}
    n = int(row.get("at_risk_customers") or 0)
    aov = float(row.get("current_aov") or 0)
    recovered = round(n * 0.15)
    impact = recovered * aov
    return {
        "id": "reactivate_at_risk",
        "priority": "high",
        "title": "Win back lapsing high-value customers",
        "finding": (
            f"{n} customers are in the top 30% by lifetime value but haven't ordered "
            f"in {int(row.get('avg_days_since_order') or 0)} days on average."
        ),
        "evidence": (
            f"At-risk customers: {n}. Lifetime net already booked from them: "
            f"{_fmt_money(row.get('lifetime_net_at_risk'))}. "
            f"Current completed-order AOV: {_fmt_money(aov)}."
        ),
        "recommendation": (
            "Launch a targeted win-back flow for this exact list (email + SMS), "
            "with a time-boxed incentive and a reminder of previously purchased "
            "categories."
        ),
        "expected_impact": (
            f"A 15% reactivation rate = {recovered} customers x {_fmt_money(aov)} AOV "
            f"= {_fmt_money(impact)} in near-term revenue, before downstream repeat orders."
        ),
        "next_step": (
            "Export the at-risk list from Customer Analytics → 'At-risk customers', "
            "hand it to lifecycle marketing, and hold out 10% as a control."
        ),
    }


def _channel_repeat_gap() -> dict[str, Any]:
    rows = fetch_all(
        """
        WITH pc AS (
            SELECT c.customer_id, c.acquisition_channel,
                   count(o.order_id) FILTER (WHERE o.status = 'completed') AS completed
            FROM customers c
            LEFT JOIN orders o ON o.customer_id = c.customer_id
            GROUP BY c.customer_id, c.acquisition_channel
        )
        SELECT acquisition_channel,
               count(*) FILTER (WHERE completed >= 1) AS buyers,
               round(100.0 * count(*) FILTER (WHERE completed >= 2)
                     / NULLIF(count(*) FILTER (WHERE completed >= 1), 0), 1) AS repeat_rate_pct
        FROM pc
        GROUP BY acquisition_channel
        HAVING count(*) FILTER (WHERE completed >= 1) > 0
        ORDER BY repeat_rate_pct
        """
    )
    if not rows:
        return {}
    worst, best = rows[0], rows[-1]
    gap = float(best["repeat_rate_pct"] or 0) - float(worst["repeat_rate_pct"] or 0)
    return {
        "id": "channel_repeat_gap",
        "priority": "medium",
        "title": f"Fix the repeat-rate gap on '{worst['acquisition_channel']}' acquisition",
        "finding": (
            f"'{worst['acquisition_channel']}' customers repeat at "
            f"{worst['repeat_rate_pct']}% vs {best['repeat_rate_pct']}% for "
            f"'{best['acquisition_channel']}' — a {gap:.1f} pt gap."
        ),
        "evidence": "; ".join(
            f"{r['acquisition_channel']}: {r['repeat_rate_pct']}% repeat over {r['buyers']} buyers"
            for r in rows
        ),
        "recommendation": (
            f"Add a second-purchase nudge (welcome series + first-reorder offer) "
            f"scoped to '{worst['acquisition_channel']}', and review whether that "
            f"channel is buying low-intent traffic."
        ),
        "expected_impact": (
            f"Closing half the gap ({gap / 2:.1f} pt) on {worst['buyers']} buyers "
            f"= ~{round(worst['buyers'] * gap / 200)} extra repeat customers."
        ),
        "next_step": "A/B test the second-purchase offer on this channel for 4 weeks.",
    }


def _campaign_spend_efficiency() -> dict[str, Any]:
    rows = fetch_all(
        """
        WITH f AS (
            SELECT campaign_id,
                   count(*) FILTER (WHERE event_type = 'sent')     AS sent,
                   count(*) FILTER (WHERE event_type = 'convert')  AS conv,
                   sum(revenue) FILTER (WHERE event_type = 'convert') AS rev
            FROM campaign_events GROUP BY campaign_id
        )
        SELECT c.campaign_name, c.channel, c.budget,
               f.sent, f.conv,
               round(100.0 * f.conv / NULLIF(f.sent, 0), 2) AS conv_rate_pct,
               round(f.rev, 2) AS revenue,
               round(f.rev / NULLIF(c.budget, 0), 2) AS roas
        FROM campaigns c JOIN f ON f.campaign_id = c.campaign_id
        ORDER BY roas ASC NULLS FIRST
        """
    )
    if not rows:
        return {}
    worst = [r for r in rows if r["roas"] is not None][:3]
    best = [r for r in rows if r["roas"] is not None][-3:]
    wasted = sum(float(r["budget"] or 0) for r in worst)
    return {
        "id": "campaign_spend_efficiency",
        "priority": "high",
        "title": "Reallocate budget from the lowest-ROAS campaigns",
        "finding": (
            f"The 3 weakest campaigns return ROAS of "
            f"{', '.join(str(r['roas']) for r in worst)} against combined budget "
            f"{_fmt_money(wasted)}."
        ),
        "evidence": "; ".join(
            f"{r['campaign_name']} ({r['channel']}): ROAS {r['roas']}, "
            f"conv {r['conv_rate_pct']}%, revenue {_fmt_money(r['revenue'])}"
            for r in worst + best
        ),
        "recommendation": (
            "Pause or rework the bottom 3 campaigns and shift budget toward the "
            f"top performers ({', '.join(r['campaign_name'] for r in best)})."
        ),
        "expected_impact": (
            f"Moving {_fmt_money(wasted)} from ROAS ~{worst[0]['roas']} to the "
            f"top-campaign ROAS ~{best[-1]['roas']} implies roughly "
            f"{_fmt_money(wasted * (float(best[-1]['roas'] or 0) - float(worst[0]['roas'] or 0)))} "
            "of incremental attributed revenue."
        ),
        "next_step": "Confirm attribution window with marketing, then rebalance next cycle.",
    }


def _returns_leakage() -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT
          count(*) FILTER (WHERE status = 'returned')                          AS returned_orders,
          count(*) FILTER (WHERE status = 'completed')                         AS completed_orders,
          round(100.0 * count(*) FILTER (WHERE status = 'returned')
                / NULLIF(count(*) FILTER (WHERE status IN ('completed','returned')), 0), 2) AS return_rate_pct,
          round(sum(gross_amount) FILTER (WHERE status = 'returned'), 2)       AS returned_gross
        FROM orders
        """
    ) or {}
    return {
        "id": "returns_leakage",
        "priority": "medium",
        "title": "Quantify and attack return-driven revenue leakage",
        "finding": (
            f"Return rate is {row.get('return_rate_pct')}% "
            f"({row.get('returned_orders')} of "
            f"{int(row.get('returned_orders') or 0) + int(row.get('completed_orders') or 0)} "
            "resolved orders)."
        ),
        "evidence": (
            f"Returned orders: {row.get('returned_orders')}. "
            f"Gross value returned: {_fmt_money(row.get('returned_gross'))}."
        ),
        "recommendation": (
            "Break returns down by product category and channel (see SQL Workspace), "
            "then tighten sizing guidance / imagery for the worst offenders."
        ),
        "expected_impact": (
            f"Cutting the return rate by 1 pt recovers about "
            f"{_fmt_money(float(row.get('returned_gross') or 0) / max(float(row.get('return_rate_pct') or 1), 1))} "
            "of gross value per point."
        ),
        "next_step": "Add a returns-by-category query to the weekly review.",
    }


def all_recommendations() -> dict[str, Any]:
    started = time.perf_counter()
    items = [
        _at_risk_reactivation(),
        _campaign_spend_efficiency(),
        _channel_repeat_gap(),
        _returns_leakage(),
    ]
    items = [i for i in items if i]
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "count": len(items),
        "recommendations": items,
        "note": "Every figure in 'evidence' was returned by SQL during this request.",
    }
