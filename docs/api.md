# API reference

Base URL: `http://localhost:8000/api` · Interactive: `http://localhost:8000/docs`

All responses are JSON. Domain errors return `{"ok": false, "error": "..."}`
(HTTP 200 or 4xx); unexpected errors return HTTP 500 with the same shape.

---

## Meta

### `GET /api/health`
`{ "status": "ok", "version": "1.0.0" }`

### `GET /api/ready`
`{ "status": "ok", "db": "up", "seeded": true }` — `seeded` is false until the
seed finishes.

### `GET /api/meta`
```json
{
  "version": "1.0.0",
  "ai_enabled": false,
  "ai_model": null,
  "query_row_limit": 1000,
  "statement_timeout_ms": 8000,
  "allowed_tables": ["campaign_events", "campaign_events_part", "campaigns",
                     "customers", "etl_runs", "order_items", "orders", "products"]
}
```

---

## Dashboard

### `GET /api/dashboard/summary?refresh=false`
```jsonc
{
  "generated_at": "2026-09-10T12:00:00Z",
  "build_ms": 84.2,
  "cached": false,
  "kpis": {
    "total_customers": 60000, "buyers": 41988, "repeat_buyers": 30110,
    "repeat_purchase_rate_pct": 71.7, "active_customers_90d": 5123,
    "completed_orders": 331204, "avg_order_value": 8421.55,
    "total_net_revenue": 2790000000.0, "net_revenue_30d": 1234567.0,
    "revenue_mom_growth_pct": 3.4,
    "prior_window_buyers": 8800, "retained": 3960, "retention_rate_pct": 45.0
  },
  "campaign_conversion": { "sent": 1234000, "clicks": 42000, "conversions": 8000,
                           "conversion_rate_pct": 0.65, "attributed_revenue": 24000000.0 },
  "at_risk": { "at_risk_customers": 3120, "lifetime_net_at_risk": 88000000.0,
               "avg_days_since_order": 190 },
  "revenue_trend": [ { "month": "2025-10", "net_revenue": 1200000.0, "orders": 142 } ],
  "segment_performance": [ { "segment": "Champions", "customers": 4200,
                             "avg_orders": 9.1, "avg_lifetime_net": 120000.0,
                             "segment_lifetime_net": 504000000.0 } ],
  "data_freshness": { "latest_order": "...", "order_lag": "...", "last_successful_etl": "..." }
}
```

---

## SQL Workspace

### `GET /api/workspace/catalog`
`{ "count": 10, "queries": [ { "id", "name", "question", "tags", "techniques", "sql" } ] }`

### `POST /api/workspace/run`
Body — **one of**:
```json
{ "query_id": "01_revenue_trend", "explain": true }
{ "sql": "SELECT ... ", "explain": true }
```
Success:
```jsonc
{
  "ok": true, "source": "custom",
  "sql": "SELECT ...",                // as written
  "executed_sql": "SELECT * FROM ( ... ) AS _xeno_capped LIMIT 1000",
  "tables": ["orders"],
  "columns": ["month", "net_revenue"],
  "rows": [ { "month": "2025-10", "net_revenue": 1200000.0 } ],
  "row_count": 12, "truncated": false, "execution_ms": 6.4,
  "plan": [ { "Plan": { "...": "EXPLAIN (ANALYZE, BUFFERS) JSON" } } ],
  "plan_meta": { "planning_ms": 0.3, "execution_ms": 6.1, "total_cost": 812.4,
                 "top_node": "Sort", "actual_rows": 12 }
}
```
Rejected (guard) → `{ "ok": false, "source": "custom", "sql": "...", "error": "Table 'pg_user' is not allow-listed. ..." }`

---

## Query Performance Lab

### `GET /api/performance/scenarios`
```jsonc
{ "scenarios": [ {
  "id": "index_event_type_time", "title": "...", "category": "Indexing",
  "problem": "...", "technique": "...", "takeaway": "...",
  "query_before": "SELECT ...", "query_after": "SELECT ...",
  "available": true, "unavailable_reason": null
} ] }
```

### `POST /api/performance/scenarios/{id}/benchmark`
Runs real `EXPLAIN (ANALYZE, BUFFERS)` before and after the optimisation.
```jsonc
{
  "scenario_id": "index_event_type_time", "title": "...", "category": "Indexing",
  "before": { "execution_ms": 480.2, "scan_types": ["Seq Scan"],
              "buffers_total": 18234, "has_seq_scan": true,
              "has_index_only_scan": false, "plan": [ ... ] },
  "after":  { "execution_ms": 12.7, "scan_types": ["Index Only Scan"],
              "buffers_total": 91, "has_seq_scan": false,
              "has_index_only_scan": true, "plan": [ ... ] },
  "comparison": {
    "execution_ms_before": 480.2, "execution_ms_after": 12.7, "speedup_x": 37.8,
    "buffers_before": 18234, "buffers_after": 91, "buffer_reduction_x": 200.4,
    "seq_scan_removed": true, "became_index_only": true, "partitions_pruned_after": 0
  },
  "wall_ms": 2410.0
}
```
Numbers above are illustrative shape only — actual values come from your machine.

### `POST /api/performance/scaling-benchmark`
```jsonc
{
  "windows_days": [30, 180, 730, 3650],
  "results": {
    "with_index":    [ { "window_days": 30, "execution_ms": 1.9, "rows_returned": 46, "buffers_total": 55, "scan_types": ["Index Only Scan"] } ],
    "without_index": [ { "window_days": 30, "execution_ms": 470.0, "rows_returned": 46, "buffers_total": 18000, "scan_types": ["Seq Scan"] } ]
  }
}
```

---

## Customer Analytics

### `GET /api/customers/analyses`
List of `{ key, query_id, name }`.

### `GET /api/customers/{analysis}`
`analysis` ∈ `rfm | cohort | at_risk | churn | repeat_by_channel | campaign_by_segment`
```jsonc
{ "ok": true, "id": "02_rfm_segments", "name": "RFM segmentation",
  "question": "...", "techniques": ["NTILE window functions", "..."],
  "sql": "WITH base AS ( ... )",
  "columns": [ ... ], "rows": [ ... ], "row_count": 8, "execution_ms": 210.4 }
```

---

## AI Analyst

### `GET /api/ai/examples`
`{ "examples": [ "What is our repeat purchase rate?", ... ] }`

### `POST /api/ai/ask`
Body: `{ "question": "Which campaigns have the best ROAS?", "execute": true }`
```jsonc
{
  "ok": true, "question": "...",
  "engine": "rule-based",            // or "llm"
  "model": "catalog:05_campaign_funnel",
  "summary_engine": "template",       // or "llm"
  "sql": "WITH f AS ( ... )",
  "executed_sql": "SELECT * FROM ( ... ) AS _xeno_capped LIMIT 1000",
  "sql_valid": true, "tables": ["campaigns", "campaign_events"],
  "columns": [ ... ], "rows": [ ... ], "row_count": 20, "execution_ms": 88.1,
  "summary": "Query returned 20 rows ...",
  "recommendation": { "finding": "...", "evidence": "...", "recommendation": "...",
                      "expected_impact": "...", "next_step": "..." },
  "disclaimer": "Numbers are computed live ... No values ... are estimated or invented."
}
```
Failure modes: `{"ok": false, "error": "Could not map this question ..."}` or
`{"ok": false, "sql_valid": false, "validation_error": "...", "error": "Generated SQL failed the read-only guard and was not executed."}`

---

## Data Quality

### `GET /api/data-quality/checks`
```jsonc
{
  "summary": { "total": 12, "passed": 10, "failed": 2, "warnings": 0, "health_score": 83.3 },
  "checks": [ {
    "id": "duplicate_orders", "title": "Likely duplicate orders ...",
    "category": "uniqueness", "severity": "high",
    "metric": 120, "threshold": 0, "status": "fail",
    "detail": [ { "customer_id": 42, "order_date": "...", "net_amount": 8123.0,
                  "duplicate_rows": 2, "order_ids": [101, 410233] } ]
  } ]
}
```

---

## Session (anonymous, cookie-based)

All endpoints read/set the `xeno_session` cookie: `<session_id>.<hmac-sha256>`,
HttpOnly, `SameSite=Lax`, `Secure` off by default (set `SESSION_COOKIE_SECURE=true`
behind HTTPS), 30-day TTL. No login, no personal data. Send `credentials:
"include"` (the frontend does).

### `GET /api/session`
Loads or creates the caller's session; refreshes `last_seen_at` and the cookie.
```jsonc
{
  "session_id": "T0QCe…", "short_id": "T0QCeRmk",
  "created_at": "...", "last_seen_at": "...",
  "tour_completed": false, "preferences": {}, "request_count": 2, "is_new": true,
  "recent_queries": [
    { "id": 12, "sql": "WITH pc AS (...)", "source": "catalog",
      "row_count": 5, "execution_ms": 41.2, "ok": true, "created_at": "..." }
  ],
  "cookie": { "name": "xeno_session", "httponly": true, "samesite": "lax",
              "secure": false, "ttl_days": 30, "signed": "HMAC-SHA256" }
}
```

### `POST /api/session/tour`
Body `{ "completed": true }` → `{ "session_id": "...", "tour_completed": true }`.

### `PATCH /api/session/preferences`
Body `{ "patch": { "lastPage": "/performance" } }` → `{ "preferences": { ... } }`
(shallow-merged into the stored JSON).

### `GET /api/session/queries`
`{ "queries": [ ...recent SQL Workspace runs for this session... ] }`

### `DELETE /api/session`
Deletes the row and clears the cookie → `{ "ok": true, "cleared": "T0QCeRmk" }`.

`POST /api/workspace/run` also depends on the session — every run (or rejection)
is appended to `session_queries`, capped at `SESSION_QUERY_HISTORY` (25).

---

## Recommendations

### `GET /api/recommendations`
```jsonc
{
  "count": 4,
  "recommendations": [ {
    "id": "reactivate_at_risk", "priority": "high", "title": "...",
    "finding": "...", "evidence": "At-risk customers: 3120. Lifetime net ...: ₹88,000,000. ...",
    "recommendation": "...", "expected_impact": "A 15% reactivation rate = 468 customers x ₹8,421 AOV = ₹3,941,000 ...",
    "next_step": "..."
  } ],
  "note": "Every figure in 'evidence' was returned by SQL during this request."
}
```
