# XenoPulse — AI-Native Retail Analytics Platform

A full-stack analytics application for a retail / loyalty business. It turns raw
customer, order and campaign data into **business insights, query-performance
diagnostics and AI-assisted analysis**.

> **All data in this project is synthetic** and generated locally by
> [`db/seed.sql`](db/seed.sql). Every metric, benchmark and AI answer is computed
> live from that database — nothing is hardcoded, mocked or fabricated.

Built to demonstrate, end to end: **SQL depth, query-performance diagnosis,
customer analytics, a guarded natural-language-to-SQL workflow, and ownership of
the business outcome behind each number.**

---

## Contents

- [Feature tour](#feature-tour)
- [Architecture](#architecture)
- [Quick start](#quick-start-docker)
- [Local development](#local-development)
- [Database](#database)
- [Query optimization examples](#query-optimization-examples)
- [Security model for user SQL](#security-model-for-user-supplied-sql)
- [API](#api)
- [Tests](#tests)
- [Deployment](#deployment)
- [Project layout](#project-layout)

---

## Feature tour

| Page | What it does | Backed by |
|---|---|---|
| **Dashboard** | Total customers, repeat-purchase rate, 90-day retention, AOV, revenue trend, campaign conversion rate, revenue at risk, segment performance | `services/metrics.py` — one SQL pass + focused follow-ups |
| **SQL Workspace** | Run a reviewed analytical query from the catalog, or write your own read-only SQL. Shows SQL, results, execution time, rows, and `EXPLAIN (ANALYZE, BUFFERS)` | `routers/workspace.py`, `db/queries/*.sql` |
| **Query Performance Lab** | Real before/after benchmarks: drop an index → `EXPLAIN ANALYZE` → create it → `EXPLAIN ANALYZE` again. Covers indexing, filter-before-join, avoiding `SELECT *`, aggregation on covering indexes, partition pruning, and a dataset-size scaling sweep | `services/perf_lab.py` |
| **Customer Analytics** | RFM segmentation (NTILE), monthly cohort retention, churn/inactivity buckets, at-risk high-value identification, campaign performance by segment | `db/queries/*.sql` via `routers/customers.py` |
| **AI Analyst** | Ask in English → generate SQL → **validate** → run read-only → summarise the *actual* rows → give a Finding / Evidence / Recommendation / Expected impact / Next step | `services/ai_analyst.py` |
| **Data Quality** | 12 SQL checks: missing values, duplicate IDs, invalid/future dates, duplicate orders, orphaned rows, freshness, ETL pipeline status | `services/data_quality.py` |
| **Recommendations** | Each recommendation is generated from a query run during the request; the numbers in "Evidence" are real | `services/recommendations.py` |

---

## Architecture

```mermaid
flowchart LR
  subgraph Client
    UI["React + TypeScript SPA<br/>Recharts · 7 pages"]
  end
  subgraph API["FastAPI (Python 3.12)"]
    R["Routers<br/>/dashboard /workspace /performance<br/>/customers /ai /data-quality /recommendations"]
    G["sql_guard<br/>sqlglot parse · allow-list · deny-list · row cap"]
    S["Services<br/>metrics · perf_lab · ai_analyst<br/>data_quality · recommendations"]
    CAT["Query catalog loader<br/>db/queries/*.sql"]
  end
  subgraph DB["PostgreSQL 16"]
    OWN[("owner role<br/>trusted server SQL")]
    RO[("xeno_readonly role<br/>SELECT only · read-only txn · statement_timeout")]
  end
  LLM["Anthropic API<br/>(optional — rule-based fallback)"]

  UI -->|"/api/*"| R
  R --> S
  R --> G
  S --> CAT
  S --> OWN
  G -->|"validated SELECT"| RO
  S -.->|NL→SQL + summarise| LLM
```

- **User- or AI-supplied SQL never touches the owner connection.** It is parsed,
  structurally validated, and executed on a dedicated `xeno_readonly` role inside
  an explicit `READ ONLY` transaction with a statement timeout, then rolled back.
- The **Performance Lab** runs server-defined scenario SQL only (the sole user
  input is a scenario id checked against a dictionary).
- The **AI Analyst** works with no API key via a deterministic rule-based
  NL→SQL mapper; with `ANTHROPIC_API_KEY` set it uses the LLM for generation and
  for a strictly grounded write-up.

More detail: [`docs/architecture.md`](docs/architecture.md).

---

## Quick start (Docker)

**Prerequisites:** Docker Desktop (or Docker Engine + Compose v2), and roughly
**3 GB free disk** (base images ~1.2 GB, built images ~0.7 GB, seeded database
~0.6 GB).

```bash
git clone <this-repo> xenopulse && cd xenopulse
cp .env.example .env            # optionally add ANTHROPIC_API_KEY
docker compose up -d --build
```

First boot runs schema → seed (~20–45s) → indexes. Watch it:

```bash
docker compose logs -f db
```

The partition-pruning demo table is **opt-in** (it roughly doubles the largest
table). Enable it once the stack is up:

```bash
make partition-demo
```

Then open:

| | URL |
|---|---|
| App | http://localhost:8080 |
| API docs (OpenAPI) | http://localhost:8000/docs |
| Health | http://localhost:8000/api/health |

Verify the whole thing end-to-end:

```bash
./scripts/smoke.sh              # 17 checks against the running stack
```

Tear down (keep data) `docker compose down` · wipe data `docker compose down -v`.

---

## Local development

Run Postgres in Docker, the app services on the host.

```bash
# 1. database only
docker compose up -d db

# 2. backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql://xeno:xeno@localhost:5432/xenopulse
export DATABASE_URL_RO=postgresql://xeno_readonly:xeno_readonly_pw@localhost:5432/xenopulse
uvicorn app.main:app --reload --port 8000

# 3. frontend (new shell)
cd frontend
npm install
npm run dev                     # http://localhost:5173, proxies /api -> :8000
```

---

## Database

Seven related tables (`customers`, `products`, `campaigns`, `orders`,
`order_items`, `campaign_events`, `etl_runs`) plus an optional monthly
range-partitioned `campaign_events_part`.

Default seed volume (sized so index / join / filter choices produce measurable
10×–500× differences, while still seeding in ~1–3 min):

| table | rows |
|---|---:|
| customers | ~60,000 |
| products | 2,000 |
| campaigns | 48 |
| orders | ~115,000 |
| order_items | ~345,000 |
| campaign_events | ~1,450,000 |

The seed is **pure set-based SQL** (`generate_series`) with a fixed
`setseed(0.42)` — reproducible and fast. It deliberately injects a few duplicate
customer emails and duplicate orders so the Data Quality page has real problems
to surface.

Full column reference and ER diagram: [`docs/schema.md`](docs/schema.md).

Re-seed without recreating the container:

```bash
docker compose exec -T db psql -U xeno -d xenopulse < db/seed.sql
```

---

## Query optimization examples

The Performance Lab benchmarks these live; the write-ups (with sample
`EXPLAIN ANALYZE` output) are in
[`docs/optimization-examples.md`](docs/optimization-examples.md):

1. **Indexing** — composite `(event_type, event_time) INCLUDE (…)` turns a 2M-row
   Seq Scan into a bounded Index Only Scan.
2. **Filter before join / sargable predicates** — pre-filter `orders` in a CTE
   instead of joining everything then filtering on `to_char(order_date)`.
3. **Avoid `SELECT *`** — narrow projection + covering index → Index Only Scan,
   fewer buffers.
4. **Aggregation optimization** — covering/partial index feeds the aggregate
   without heap access.
5. **Partition pruning** — monthly `RANGE` partitions make a one-month query
   touch one partition.
6. **Dataset-size scaling** — the same query over 30 / 180 / 730 / 3650-day
   windows, with and without the index, to show how each plan scales.

---

## Security model for user-supplied SQL

`backend/app/sql_guard.py` (unit-tested in
`backend/tests/test_sql_guard.py`):

1. Single statement only (no `;` chaining).
2. Parsed with **sqlglot**; the root must be `SELECT` / `WITH` / `UNION`.
3. Rejected anywhere in the tree: `INSERT/UPDATE/DELETE/MERGE`, DDL, `COPY`,
   `GRANT`, `SELECT … INTO`, `FOR UPDATE/SHARE`, and a function denylist
   (`pg_sleep`, `pg_read_file`, `dblink`, `lo_import`, …).
4. Every referenced table must be on the allow-list (the 7 base tables + the
   partitioned table); CTE names are excluded.
5. Result set hard-capped (`SELECT * FROM (…) LIMIT :n`).
6. Execution: `xeno_readonly` role (holds `SELECT` only) → `SET TRANSACTION READ
   ONLY` → `statement_timeout` → always `ROLLBACK`.

The AI Analyst runs generated SQL through the **same** guard and never executes
SQL that fails it.

---

## API

Interactive docs at `/docs`. Reference: [`docs/api.md`](docs/api.md). Highlights:

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/dashboard/summary` | all dashboard KPIs + trend + segments |
| GET | `/api/workspace/catalog` | curated analytical queries |
| POST | `/api/workspace/run` | run `{query_id}` or `{sql}` read-only; returns rows + plan |
| GET | `/api/performance/scenarios` | perf-lab scenario list |
| POST | `/api/performance/scenarios/{id}/benchmark` | real before/after `EXPLAIN ANALYZE` |
| POST | `/api/performance/scaling-benchmark` | dataset-size sweep |
| GET | `/api/customers/{rfm\|cohort\|at_risk\|churn\|repeat_by_channel\|campaign_by_segment}` | customer analytics |
| POST | `/api/ai/ask` | NL → validated SQL → results → recommendation |
| GET | `/api/data-quality/checks` | all data-quality checks |
| GET | `/api/recommendations` | evidence-backed recommendations |

---

## Tests

```bash
# fast, no database
cd backend && python -m pytest -q tests/test_sql_guard.py tests/test_catalog.py
cd frontend && npm run typecheck

# end-to-end against a running stack
./scripts/smoke.sh

# or everything wired through the Makefile
make test          # guard tests + FE typecheck
make up && make smoke
```

`tests/test_sql_guard.py` covers ~40 allow/deny cases. `tests/test_api_smoke.py`
runs against a live DB and self-skips if one isn't reachable.

---

## Deployment

Container images for `backend` (uvicorn) and `frontend` (nginx, proxies `/api`).
Any container host works — compose, ECS, Fly.io, Render, a single VM. Secrets
come only from environment variables. Step-by-step:
[`docs/deployment.md`](docs/deployment.md).

---

## Project layout

```
xeno/
├── docker-compose.yml         # db + backend + frontend
├── .env.example
├── Makefile
├── db/
│   ├── schema.sql             # tables, keys, xeno_readonly role
│   ├── seed.sql               # pure-SQL synthetic data generator
│   ├── indexes.sql            # production secondary indexes
│   ├── partitioning.sql       # monthly RANGE-partitioned demo table
│   ├── init/                  # numbered wrappers for docker-entrypoint-initdb.d
│   └── queries/               # curated analytical queries (single source of truth)
├── backend/
│   ├── app/
│   │   ├── main.py  config.py  db.py  sql_guard.py  schema_context.py  catalog.py
│   │   ├── routers/          # one module per feature area
│   │   └── services/         # metrics · perf_lab · ai_analyst · data_quality · recommendations
│   └── tests/
├── frontend/
│   └── src/
│       ├── pages/            # Dashboard, SqlWorkspace, PerformanceLab, CustomerAnalytics,
│       │                     #   AiAnalyst, DataQuality, Recommendations
│       ├── components/       # Card, StatTile, DataTable, SqlBlock, ChartCard, …
│       └── hooks/useApi.ts
├── docs/                     # architecture · schema · api · optimization-examples · deployment
└── scripts/smoke.sh
```
