"""Read-only SQL guard for user- and AI-supplied queries.

Layered defence:
  1. This module  -- parse with sqlglot, structurally prove the statement is a
     single read-only SELECT, tables are allow-listed, no dangerous functions.
  2. db.run_readonly -- executes on a role that only holds SELECT, inside an
     explicit ``READ ONLY`` transaction with a statement timeout, always rolled
     back.

If any check fails we raise ``SqlNotAllowed`` and nothing is executed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

# Base tables + demo views the workspace / AI Analyst may read.
ALLOWED_TABLES: frozenset[str] = frozenset(
    {
        "customers",
        "products",
        "campaigns",
        "orders",
        "order_items",
        "campaign_events",
        "campaign_events_part",
        "etl_runs",
    }
)

# Statement node types that must never appear anywhere in the tree.
_FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,          # catch-all: SET, COPY, VACUUM, GRANT, CALL, ...
    exp.Grant,
)

_DENY_FUNCS: frozenset[str] = frozenset(
    {
        "pg_sleep",
        "pg_read_file",
        "pg_read_binary_file",
        "pg_ls_dir",
        "pg_stat_file",
        "pg_reload_conf",
        "pg_terminate_backend",
        "pg_cancel_backend",
        "lo_import",
        "lo_export",
        "dblink",
        "dblink_exec",
        "set_config",
        "current_setting",   # can leak connection secrets in some setups
        "query_to_xml",
        "pg_read_server_files",
        "copy_from",
        "txid_current",
    }
)

# Raw-text belt-and-braces. Case-insensitive, word-ish boundaries.
_DENY_TEXT = re.compile(
    r"(?i)\b(pg_sleep|pg_read_file|pg_ls_dir|dblink|lo_import|lo_export|"
    r"copy\s|into\s+outfile|pg_terminate_backend|pg_cancel_backend|"
    r"create\s|drop\s|alter\s|grant\s|insert\s|update\s|delete\s|truncate\s|"
    r"vacuum\s|reindex\s|refresh\s+materialized)"
)


class SqlNotAllowed(ValueError):
    """Raised when a query fails validation. Message is safe to show a user."""


@dataclass
class ValidatedSql:
    original: str          # exactly what the user / model wrote
    safe_sql: str          # what we actually execute (row-capped)
    tables: list[str]
    limit_applied: int


def _strip(sql: str) -> str:
    s = sql.strip()
    while s.endswith(";"):
        s = s[:-1].rstrip()
    return s


def validate(sql: str, row_limit: int) -> ValidatedSql:
    raw = _strip(sql)
    if not raw:
        raise SqlNotAllowed("Empty query.")
    if ";" in raw:
        raise SqlNotAllowed("Multiple statements are not allowed; submit a single SELECT.")

    # 1. parse (postgres dialect). One statement only.
    try:
        statements = [s for s in sqlglot.parse(raw, read="postgres") if s is not None]
    except Exception as exc:  # noqa: BLE001 - surface a clean message
        raise SqlNotAllowed(f"Could not parse SQL: {exc}") from exc
    if len(statements) != 1:
        raise SqlNotAllowed("Exactly one statement is required.")
    tree = statements[0]

    # 2. top-level must be a query
    if not isinstance(tree, (exp.Select, exp.Union, exp.Subquery, exp.With)):
        raise SqlNotAllowed(
            f"Only SELECT queries are allowed (got {tree.key.upper()})."
        )

    # 3. no write / DDL / command nodes anywhere (e.g. CTE that INSERTs)
    for node_type in _FORBIDDEN_NODES:
        bad = tree.find(node_type)
        if bad is not None:
            raise SqlNotAllowed(
                f"Statement type '{bad.key.upper()}' is not permitted. Read-only SELECT only."
            )

    # 4. no SELECT ... INTO (creates a table)
    for select in tree.find_all(exp.Select):
        if select.args.get("into"):
            raise SqlNotAllowed("SELECT ... INTO is not permitted.")

    # 5. no row locking
    if tree.find(exp.Lock) is not None:
        raise SqlNotAllowed("Locking clauses (FOR UPDATE / FOR SHARE) are not permitted.")

    # 6. table allow-list (exclude CTE names which are not real tables)
    cte_names = {
        (c.alias_or_name or "").lower()
        for c in tree.find_all(exp.CTE)
    }
    referenced: set[str] = set()
    for tbl in tree.find_all(exp.Table):
        name = (tbl.name or "").lower()
        if not name or name in cte_names:
            continue
        referenced.add(name)
        if name not in ALLOWED_TABLES:
            raise SqlNotAllowed(
                f"Table '{name}' is not allow-listed. "
                f"Allowed: {', '.join(sorted(ALLOWED_TABLES))}."
            )
    if not referenced:
        raise SqlNotAllowed("Query does not reference any known table.")

    # 7. function denylist (parsed + raw text)
    #    Non-standard functions (pg_sleep, dblink, ...) parse as exp.Anonymous.
    for fn in tree.find_all(exp.Anonymous):
        fname = (fn.name or "").lower()
        if fname in _DENY_FUNCS:
            raise SqlNotAllowed(f"Function '{fname}' is not permitted.")
    if _DENY_TEXT.search(raw):
        raise SqlNotAllowed("Query contains a disallowed keyword or function.")

    # 8. hard row cap: wrap so the outer LIMIT always wins.
    safe = f"SELECT * FROM (\n{raw}\n) AS _xeno_capped LIMIT {int(row_limit)}"

    return ValidatedSql(
        original=raw,
        safe_sql=safe,
        tables=sorted(referenced),
        limit_applied=int(row_limit),
    )
