"""The curated query catalog should load and every entry should parse as SQL."""
from __future__ import annotations

import sqlglot

from app.catalog import all_queries, load_catalog


def test_catalog_loads():
    queries = load_catalog()
    assert len(queries) >= 8, "expected the full analytical catalog to load"


def test_every_catalog_query_has_metadata_and_parses():
    for q in all_queries():
        assert q.name and q.question, f"{q.id} missing name/question"
        assert q.sql.strip(), f"{q.id} has no SQL"
        # must be parseable postgres and a single statement
        parsed = [s for s in sqlglot.parse(q.sql, read="postgres") if s is not None]
        assert len(parsed) == 1, f"{q.id} is not a single statement"
        assert parsed[0].key in {"select", "union", "with", "subquery"}, (
            f"{q.id} is not a SELECT-shaped query"
        )


def test_catalog_ids_are_unique():
    ids = [q.id for q in all_queries()]
    assert len(ids) == len(set(ids))


def test_every_catalog_query_passes_the_readonly_guard():
    """The AI Analyst's rule-based fallback returns catalog SQL, which is then
    re-validated by sql_guard before execution. So every catalog query must pass
    the guard cleanly."""
    from app.sql_guard import validate

    for q in all_queries():
        v = validate(q.sql, 1000)
        assert v.tables, f"{q.id}: guard found no tables"
        assert v.safe_sql.rstrip().endswith("LIMIT 1000")
