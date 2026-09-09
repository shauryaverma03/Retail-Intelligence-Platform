"""Loads the curated analytical query catalog from ``db/queries/*.sql``.

Each file starts with a metadata header of ``-- key: value`` lines:

    -- name: Monthly revenue trend (last 18 months)
    -- question: How has monthly net revenue trended ...
    -- tags: revenue, trend
    -- techniques: date_trunc, generate_series gap-fill, window
    <blank line>
    <SQL>

These queries are trusted (authored in-repo, reviewed) so they run on the
read-only pool WITHOUT going through sql_guard -- but they are still read-only
SELECTs and still time-limited.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

_HEADER_KEYS = {"name", "question", "tags", "techniques"}


def _catalog_dir() -> Path:
    """Resolve the query catalog directory across dev / container layouts."""
    try:
        from .config import get_settings

        configured = get_settings().query_catalog_dir
    except Exception:  # noqa: BLE001 - config not importable in isolated tests
        configured = "db/queries"

    here = Path(__file__).resolve()
    candidates = [
        Path(configured),
        Path.cwd() / configured,
        here.parent.parent / configured,          # backend/db/queries
        here.parents[2] / "db" / "queries",       # <repo>/db/queries
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path(configured)


@dataclass
class CatalogQuery:
    id: str
    name: str
    question: str
    tags: list[str] = field(default_factory=list)
    techniques: list[str] = field(default_factory=list)
    sql: str = ""

    def public(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "question": self.question,
            "tags": self.tags,
            "techniques": self.techniques,
            "sql": self.sql,
        }


_CATALOG: dict[str, CatalogQuery] = {}


def _parse_file(path: Path) -> CatalogQuery:
    meta: dict[str, str] = {}
    body_lines: list[str] = []
    in_body = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not in_body and line.startswith("--") and ":" in line:
            key, _, value = line[2:].strip().partition(":")
            key = key.strip().lower()
            if key in _HEADER_KEYS:
                meta[key] = value.strip()
                continue
            # a "-- comment:" style line that isn't a known key -> body starts
            in_body = True
            body_lines.append(line)
        else:
            in_body = True
            body_lines.append(line)

    sql = "\n".join(body_lines).strip()
    # drop trailing semicolons so the SQL can be safely wrapped in a subquery
    while sql.endswith(";"):
        sql = sql[:-1].rstrip()
    qid = path.stem
    return CatalogQuery(
        id=qid,
        name=meta.get("name", qid),
        question=meta.get("question", ""),
        tags=[t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
        techniques=[t.strip() for t in meta.get("techniques", "").split(",") if t.strip()],
        sql=sql,
    )


def load_catalog() -> dict[str, CatalogQuery]:
    _CATALOG.clear()
    root = _catalog_dir()
    if not root.exists():
        return _CATALOG
    for path in sorted(root.glob("*.sql")):
        q = _parse_file(path)
        if q.sql:
            _CATALOG[q.id] = q
    return _CATALOG


def all_queries() -> list[CatalogQuery]:
    if not _CATALOG:
        load_catalog()
    return list(_CATALOG.values())


def get_query(qid: str) -> CatalogQuery | None:
    if not _CATALOG:
        load_catalog()
    return _CATALOG.get(qid)
