"""Schema description handed to the LLM for natural-language-to-SQL.

Kept deliberately compact and column-accurate. The allow-list here MUST stay in
sync with sql_guard.ALLOWED_TABLES.
"""
from __future__ import annotations

SCHEMA_DDL = """
-- PostgreSQL. All data is SYNTHETIC. Read-only SELECT queries only.

customers(
  customer_id BIGINT PK, full_name TEXT, email TEXT NULL, city TEXT, region TEXT,
  country TEXT, acquisition_channel TEXT,        -- organic|paid_search|social|referral|email
  signup_date DATE, birth_year INT NULL, created_at TIMESTAMPTZ
)

products(
  product_id BIGINT PK, sku TEXT, product_name TEXT, category TEXT, subcategory TEXT,
  unit_price NUMERIC, unit_cost NUMERIC, is_active BOOL, launch_date DATE
)

campaigns(
  campaign_id BIGINT PK, campaign_name TEXT, channel TEXT,   -- email|sms|push|social|paid_search
  objective TEXT,                                            -- acquisition|retention|winback|upsell
  start_date DATE, end_date DATE, budget NUMERIC
)

orders(
  order_id BIGINT PK, customer_id BIGINT FK->customers, order_date TIMESTAMPTZ,
  status TEXT,          -- completed|returned|cancelled|pending   (revenue = completed only)
  channel TEXT,         -- web|mobile_app|store|marketplace
  ship_region TEXT, discount_amount NUMERIC, shipping_fee NUMERIC,
  gross_amount NUMERIC, net_amount NUMERIC,     -- net_amount is the revenue column
  campaign_id BIGINT NULL FK->campaigns, created_at TIMESTAMPTZ
)

order_items(
  order_item_id BIGINT PK, order_id BIGINT FK->orders, product_id BIGINT FK->products,
  quantity INT, unit_price NUMERIC, line_total NUMERIC
)

campaign_events(
  event_id BIGINT PK, campaign_id BIGINT FK->campaigns, customer_id BIGINT FK->customers,
  event_type TEXT,     -- sent|delivered|open|click|convert|unsubscribe
  event_time TIMESTAMPTZ, order_id BIGINT NULL FK->orders, revenue NUMERIC  -- >0 only on 'convert'
)

etl_runs(
  run_id BIGINT PK, pipeline TEXT, status TEXT, started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ NULL, rows_loaded BIGINT NULL, message TEXT
)
""".strip()

RULES = """
Rules for the SQL you generate:
- PostgreSQL dialect. A SINGLE read-only SELECT statement. No INSERT/UPDATE/DELETE/DDL.
- Only these tables: customers, products, campaigns, orders, order_items, campaign_events, etl_runs.
- Revenue means SUM(orders.net_amount) WHERE status = 'completed', unless the user asks otherwise.
- Campaign conversion rate = convert events / sent events from campaign_events.
- Always include an explicit ORDER BY for ranked output and a LIMIT (<= 500).
- Prefer CTEs for readability. Use window functions where they fit (NTILE for RFM, LAG for growth).
- Never invent columns. If the question can't be answered from this schema, return an empty sql.
""".strip()

FEWSHOT = [
    (
        "What is our repeat purchase rate?",
        """
WITH pc AS (
  SELECT customer_id, count(*) FILTER (WHERE status='completed') AS n
  FROM orders GROUP BY customer_id
)
SELECT round(100.0 * count(*) FILTER (WHERE n >= 2)
             / NULLIF(count(*) FILTER (WHERE n >= 1), 0), 2) AS repeat_purchase_rate_pct,
       count(*) FILTER (WHERE n >= 1) AS buyers,
       count(*) FILTER (WHERE n >= 2) AS repeat_buyers
FROM pc
""".strip(),
    ),
    (
        "Show monthly revenue for the last 6 months",
        """
SELECT to_char(date_trunc('month', order_date), 'YYYY-MM') AS month,
       round(sum(net_amount), 2) AS net_revenue,
       count(*) AS orders
FROM orders
WHERE status = 'completed'
  AND order_date >= date_trunc('month', CURRENT_DATE) - interval '6 months'
GROUP BY 1 ORDER BY 1
""".strip(),
    ),
    (
        "Which campaigns have the best return on ad spend?",
        """
WITH f AS (
  SELECT campaign_id,
         count(*) FILTER (WHERE event_type='sent')    AS sent,
         count(*) FILTER (WHERE event_type='convert') AS conv,
         sum(revenue) FILTER (WHERE event_type='convert') AS revenue
  FROM campaign_events GROUP BY campaign_id
)
SELECT c.campaign_name, c.channel,
       round(100.0 * f.conv / NULLIF(f.sent,0), 2) AS conversion_rate_pct,
       round(f.revenue, 2) AS attributed_revenue,
       round(f.revenue / NULLIF(c.budget, 0), 2) AS roas
FROM campaigns c JOIN f ON f.campaign_id = c.campaign_id
ORDER BY roas DESC NULLS LAST
LIMIT 20
""".strip(),
    ),
]


def build_system_prompt() -> str:
    shots = "\n\n".join(
        f"Q: {q}\nSQL:\n{sql}" for q, sql in FEWSHOT
    )
    return (
        "You translate retail-analytics questions into PostgreSQL.\n\n"
        f"SCHEMA:\n{SCHEMA_DDL}\n\n{RULES}\n\n"
        f"EXAMPLES:\n{shots}\n\n"
        'Respond ONLY with minified JSON: {"sql": "<single SELECT or empty string>", '
        '"assumptions": "<one sentence>"}'
    )
