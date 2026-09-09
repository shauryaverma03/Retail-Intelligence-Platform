# Query optimization examples

These are the scenarios the **Query Performance Lab** benchmarks live. The Lab
runs `EXPLAIN (ANALYZE, BUFFERS)` against your database on both the "before" and
"after" states and reports the real numbers — this document explains *why* each
change helps and what to look for in the plan.

> The plan snippets below show the **shape** of the output (node types, the
> before→after transition). Absolute timings depend on your hardware, cache
> state and seed volume — read them from the Lab, not from here.

Common setup: default seed (~1.45M `campaign_events`, ~115k `orders`,
~345k `order_items`).

---

## 1. Indexing — composite index with `INCLUDE`

**Query** (conversion revenue by campaign, last year):

```sql
SELECT ce.campaign_id, count(*) AS conversions, sum(ce.revenue) AS revenue
FROM campaign_events ce
WHERE ce.event_type = 'convert'
  AND ce.event_time >= now() - interval '365 days'
GROUP BY ce.campaign_id
ORDER BY revenue DESC;
```

**Before** (`ix_campaign_events_type_time` dropped):

```
GroupAggregate
  ->  Sort  (Sort Key: campaign_id)
        ->  Seq Scan on campaign_events ce
              Filter: (event_type = 'convert' AND event_time >= ...)
              Rows Removed by Filter: ~2.0M
              Buffers: shared read ~18k
```

**After** `CREATE INDEX ix_campaign_events_type_time ON campaign_events
(event_type, event_time) INCLUDE (campaign_id, revenue)`:

```
GroupAggregate
  ->  Index Only Scan using ix_campaign_events_type_time on campaign_events ce
        Index Cond: (event_type = 'convert' AND event_time >= ...)
        Heap Fetches: 0
        Buffers: shared hit ~90
```

**Why:** the leading column (`event_type`) narrows to ~4% of the table, the
second column (`event_time`) bounds the range, and because `campaign_id` and
`revenue` are in the `INCLUDE` payload the executor never touches the heap
(`Heap Fetches: 0`). Seq Scan → Index Only Scan; buffers collapse by ~2 orders
of magnitude.

**Rule of thumb:** index on `(equality_col, range_col)` and `INCLUDE` the columns
the query still needs, so the scan stays index-only.

---

## 2. Filter before the join, and keep predicates sargable

**Before** — join everything, then filter, with a non-sargable date predicate:

```sql
SELECT p.category, sum(oi.line_total) AS revenue, count(DISTINCT o.order_id) AS orders
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p     ON p.product_id = oi.product_id
WHERE to_char(o.order_date, 'YYYY-MM-DD') >= to_char(now() - interval '45 days', 'YYYY-MM-DD')
  AND o.status = 'completed'
GROUP BY p.category
ORDER BY revenue DESC;
```

```
HashAggregate
  ->  Hash Join  (oi.product_id = p.product_id)
        ->  Hash Join  (oi.order_id = o.order_id)
              ->  Seq Scan on order_items oi          -- the whole table materialised
              ->  Hash
                    ->  Seq Scan on orders o
                          Filter: (to_char(order_date, ...) >= ... )   -- index unusable
```

`to_char(order_date, …)` wraps the column in a function, so
`ix_orders_completed_date` can't be used; the whole `order_items` table feeds the
join before anything is discarded.

**After** — pre-filter `orders` in a CTE with a plain range predicate:

```sql
WITH recent_orders AS (
    SELECT o.order_id
    FROM orders o
    WHERE o.order_date >= now() - interval '45 days'
      AND o.status = 'completed'
)
SELECT p.category, sum(oi.line_total) AS revenue, count(DISTINCT oi.order_id) AS orders
FROM recent_orders ro
JOIN order_items oi ON oi.order_id = ro.order_id
JOIN products p     ON p.product_id = oi.product_id
GROUP BY p.category
ORDER BY revenue DESC;
```

```
HashAggregate
  ->  Hash Join  (oi.product_id = p.product_id)
        ->  Nested Loop  (ro.order_id = oi.order_id)
              ->  Index Scan using ix_orders_completed_date on orders o   -- days, not full table
              ->  Index Scan using ix_order_items_order_id on order_items oi
```

**Why:** the sargable predicate lets the planner range-scan `orders` for ~45
days of rows, and the join now probes `order_items` only for those orders. The
driving row count drops from "whole table" to "recent slice".

---

## 3. Avoid `SELECT *`

**Before:**

```sql
SELECT *
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.customer_id BETWEEN 1000 AND 3000;
```

Every column of both wide tables is projected and every matching heap page is
read. `SELECT *` also silently prevents Index Only Scans — the moment one column
isn't in the index, the executor must visit the heap.

**After** — ask for exactly what the report uses, backed by a covering index:

```sql
-- CREATE INDEX ix_orders_cust_status_incl
--   ON orders (customer_id, status) INCLUDE (net_amount, order_date);

SELECT o.order_id, o.customer_id, o.net_amount
FROM orders o
WHERE o.customer_id BETWEEN 1000 AND 3000
  AND o.status = 'completed';
```

```
Index Only Scan using ix_orders_cust_status_incl on orders o
  Index Cond: (customer_id >= 1000 AND customer_id <= 3000 AND status = 'completed')
  Heap Fetches: 0
```

**Why:** narrow projection means fewer bytes through every operator, and the
covering index answers the query without heap access. Watch the `Buffers` line
drop in the Lab.

---

## 4. Aggregation on a covering / partial index

**Query** (customer lifetime value):

```sql
SELECT o.customer_id, sum(o.net_amount) AS lifetime_net, count(*) AS orders
FROM orders o
WHERE o.status = 'completed'
GROUP BY o.customer_id;
```

**Before** (no covering index):

```
HashAggregate  (Group Key: customer_id)
  ->  Seq Scan on orders o
        Filter: (status = 'completed')
        Buffers: shared read ~7k
```

**After** (`ix_orders_cust_status_incl` present):

```
GroupAggregate  (Group Key: customer_id)
  ->  Index Only Scan using ix_orders_cust_status_incl on orders o
        Index Cond: (status = 'completed')
        Heap Fetches: 0
```

**Why:** the index already stores `customer_id` (sort order) and `net_amount`
(the payload), so the aggregate reads pre-sorted, heap-free input and can stream
a `GroupAggregate` instead of building a hash table. The partial/covering shape
does two jobs: skip non-`completed` rows and avoid the heap.

---

## 5. Partition pruning

Requires `campaign_events_part` (built by `db/partitioning.sql`). It is **not**
part of the default init (it roughly doubles the size of the largest table).
Enable it with `make partition-demo` (or
`docker compose exec -T db psql -U xeno -d xenopulse < db/partitioning.sql`).
Until then the Performance Lab shows this scenario as "unavailable" with that
instruction.

**Query** (one month of events):

```sql
SELECT date_trunc('day', event_time) AS day, count(*), sum(revenue)
FROM campaign_events_part           -- vs campaign_events (unpartitioned)
WHERE event_time >= date '2024-06-01' AND event_time < date '2024-07-01'
GROUP BY 1 ORDER BY 1;
```

**Unpartitioned** — one relation, whole thing scanned/filtered:

```
Seq Scan on campaign_events   (Rows Removed by Filter: most of ~1.45M)
```

**Partitioned** — planner keeps only the June 2024 partition:

```
Append
  Subplans Removed: 48
  ->  Index Scan using campaign_events_p202406_event_time_idx on campaign_events_p202406
```

**Why:** with monthly `RANGE (event_time)` partitions, a bounded time predicate
lets the planner discard non-overlapping partitions at plan time
(`Subplans Removed`). Scan cost becomes proportional to the queried window, not
to total history — the pattern for time-series / event tables that grow forever.

---

## 6. Dataset-size scaling sweep

`POST /api/performance/scaling-benchmark` runs query #1 over 30 / 180 / 730 /
3650-day windows, once with `ix_campaign_events_type_time` dropped and once with
it present — eight `EXPLAIN ANALYZE` runs.

What the numbers show:

- **Without the index:** execution time is roughly flat and high across all
  windows — a Seq Scan pays for the whole table regardless of how selective the
  filter is.
- **With the index:** execution time tracks the number of matched rows — tiny for
  30 days, larger (but still far below the Seq Scan) for 10 years.

This is the concrete version of "an index helps *more* as the table grows and the
query stays selective".

---

## General checklist applied throughout this project

| Symptom in `EXPLAIN ANALYZE` | Usual fix |
|---|---|
| `Seq Scan` + high `Rows Removed by Filter` | index the filter columns (equality first, then range) |
| `Heap Fetches` > 0 on an Index Only Scan | add the missing columns to `INCLUDE` |
| Big join input then `Rows Removed by Filter` above it | filter in a CTE / subquery *before* the join |
| Function around a column in `WHERE` / `JOIN` | rewrite to a sargable predicate (`col >= x`, not `f(col) = y`) |
| Wide rows through every node | project only needed columns; drop `SELECT *` |
| `HashAggregate` spilling (`Batches` > 1) | raise `work_mem` for the session, or feed it a sorted index scan |
| Whole time-series table scanned for a recent window | range-partition on the time column |
