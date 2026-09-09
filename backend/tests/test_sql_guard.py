"""Unit tests for the read-only SQL guard. No database required."""
from __future__ import annotations

import pytest

from app import sql_guard
from app.sql_guard import SqlNotAllowed, validate

ROW_LIMIT = 1000


# --------------------------------------------------------------------------
# allowed
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT count(*) FROM customers",
        "select customer_id, net_amount from orders where status = 'completed' limit 10",
        """
        WITH pc AS (SELECT customer_id, count(*) n FROM orders GROUP BY customer_id)
        SELECT round(100.0 * count(*) FILTER (WHERE n >= 2) / NULLIF(count(*),0), 2) AS pct
        FROM pc
        """,
        "SELECT c.region, sum(o.net_amount) FROM customers c JOIN orders o USING (customer_id) GROUP BY 1",
        "SELECT * FROM campaign_events WHERE event_type = 'convert' ORDER BY event_time DESC",
        "(SELECT 1 FROM orders) UNION (SELECT 2 FROM customers)",
    ],
)
def test_allows_readonly_selects(sql):
    v = validate(sql, ROW_LIMIT)
    assert v.safe_sql.strip().lower().startswith("select * from (")
    assert f"limit {ROW_LIMIT}" in v.safe_sql.lower()


def test_reports_referenced_tables():
    v = validate("SELECT * FROM orders o JOIN order_items oi USING (order_id)", ROW_LIMIT)
    assert set(v.tables) == {"orders", "order_items"}


def test_cte_names_not_treated_as_tables():
    v = validate(
        "WITH recent AS (SELECT * FROM orders) SELECT * FROM recent",
        ROW_LIMIT,
    )
    assert v.tables == ["orders"]


# --------------------------------------------------------------------------
# rejected
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO customers (full_name) VALUES ('x')",
        "UPDATE orders SET net_amount = 0",
        "DELETE FROM orders",
        "DROP TABLE customers",
        "TRUNCATE orders",
        "ALTER TABLE orders ADD COLUMN x int",
        "CREATE TABLE t (id int)",
        "GRANT SELECT ON orders TO public",
        "SELECT 1; DROP TABLE customers",
        "SELECT * FROM orders; SELECT * FROM customers",
        "SELECT pg_sleep(10)",
        "SELECT * FROM pg_read_file('/etc/passwd')",
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM pg_catalog.pg_user",
        "SELECT * FROM dblink('', 'select 1') AS t(a int)",
        "SELECT * FROM orders FOR UPDATE",
        "SELECT * INTO backup FROM orders",
        "WITH x AS (INSERT INTO orders DEFAULT VALUES RETURNING *) SELECT * FROM x",
        "COPY orders TO '/tmp/x.csv'",
        "SELECT * FROM secret_table",
        "",
        "   ",
    ],
)
def test_rejects_non_readonly_or_unlisted(sql):
    with pytest.raises(SqlNotAllowed):
        validate(sql, ROW_LIMIT)


def test_allowlist_matches_schema_context():
    from app.schema_context import SCHEMA_DDL

    for table in sql_guard.ALLOWED_TABLES:
        if table == "campaign_events_part":  # perf-lab only, not in the NL schema
            continue
        assert table in SCHEMA_DDL, f"{table} missing from schema_context"


def test_limit_is_capped_even_if_user_asks_for_more():
    v = validate("SELECT * FROM orders LIMIT 999999", ROW_LIMIT)
    # outer wrap forces the cap; inner limit is preserved but bounded
    assert v.safe_sql.rstrip().endswith(f"LIMIT {ROW_LIMIT}")
