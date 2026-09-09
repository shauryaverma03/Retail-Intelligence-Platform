#!/usr/bin/env bash
# End-to-end smoke test for a running XenoPulse stack.
# Usage: ./scripts/smoke.sh [API_BASE]   (default http://localhost:8000/api)
set -euo pipefail

API="${1:-http://localhost:8000/api}"
pass=0; fail=0

j() { python3 -c 'import sys,json;d=json.load(sys.stdin);print(eval(sys.argv[1]))' "$1"; }

check() {
  local name="$1" method="$2" path="$3" body="${4:-}"
  local expr="$5"
  local out
  if [[ "$method" == "GET" ]]; then
    out=$(curl -sS -f "$API$path") || { echo "FAIL  $name (HTTP error)"; fail=$((fail+1)); return; }
  else
    out=$(curl -sS -f -X "$method" -H 'Content-Type: application/json' -d "$body" "$API$path") \
      || { echo "FAIL  $name (HTTP error)"; fail=$((fail+1)); return; }
  fi
  if echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); assert ($expr), 'assertion failed'" 2>/dev/null; then
    echo "PASS  $name"
    pass=$((pass+1))
  else
    echo "FAIL  $name  :: $expr"
    echo "      $out" | head -c 400; echo
    fail=$((fail+1))
  fi
}

echo "== XenoPulse smoke test ($API) =="

check "health"              GET  "/health"            ""  "d['status']=='ok'"
check "ready + seeded"      GET  "/ready"             ""  "d['seeded'] is True"
check "meta"                GET  "/meta"              ""  "'orders' in d['allowed_tables']"
check "dashboard summary"   GET  "/dashboard/summary" ""  "d['kpis']['total_customers'] > 0 and len(d['revenue_trend']) >= 1"
check "workspace catalog"   GET  "/workspace/catalog" ""  "d['count'] >= 8"
check "run catalog query"   POST "/workspace/run"     '{"query_id":"01_revenue_trend","explain":true}'  "d['ok'] and d['row_count'] > 0 and d['plan'] is not None"
check "guard blocks write"  POST "/workspace/run"     '{"sql":"DROP TABLE orders"}'  "d['ok'] is False"
check "guard blocks table"  POST "/workspace/run"     '{"sql":"SELECT * FROM pg_user"}'  "d['ok'] is False"
check "custom select runs"  POST "/workspace/run"     '{"sql":"SELECT count(*) AS n FROM customers","explain":false}'  "d['ok'] and d['rows'][0]['n'] > 0"
check "perf scenarios"      GET  "/performance/scenarios" ""  "len(d['scenarios']) >= 4"
check "perf benchmark"      POST "/performance/scenarios/index_event_type_time/benchmark" '{}'  "d['comparison']['execution_ms_before'] is not None and d['comparison']['execution_ms_after'] is not None"
check "customer rfm"        GET  "/customers/rfm"     ""  "d['ok'] and d['row_count'] > 0"
check "customer cohort"     GET  "/customers/cohort"  ""  "d['ok']"
check "ai ask (rule-based)" POST "/ai/ask"            '{"question":"What is our repeat purchase rate?"}'  "d['ok'] and d['sql_valid'] and d['row_count'] >= 1"
check "ai rejects bad q"    POST "/ai/ask"            '{"question":"asdf qwerty zxcv"}'  "d['ok'] is False"
check "data quality"        GET  "/data-quality/checks" ""  "d['summary']['total'] >= 8"
check "recommendations"     GET  "/recommendations"   ""  "d['count'] >= 1 and all(r['evidence'] for r in d['recommendations'])"

# --- session / cookie flow (needs a cookie jar) --------------------------------
CJ="$(mktemp)"
assert_json() { python3 -c "import sys,json; d=json.load(sys.stdin); assert ($1), 'assertion failed'"; }
sess_check() {
  local name="$1" expr="$2"; shift 2
  if curl -sS -f -c "$CJ" -b "$CJ" "$@" | assert_json "$expr" 2>/dev/null; then
    echo "PASS  $name"; pass=$((pass+1))
  else
    echo "FAIL  $name :: $expr"; fail=$((fail+1))
  fi
}

sess_check "session issues cookie" \
  "d['is_new'] is True and len(d['session_id']) >= 16" \
  "$API/session"
grep -q xeno_session "$CJ" && { echo "PASS  session cookie stored"; pass=$((pass+1)); } \
                           || { echo "FAIL  session cookie stored"; fail=$((fail+1)); }
sess_check "workspace run recorded on session" \
  "d['ok'] is True" \
  -X POST -H 'Content-Type: application/json' \
  -d '{"query_id":"07_repeat_purchase_rate","explain":false}' "$API/workspace/run"
sess_check "session history has the query" \
  "len(d['recent_queries']) >= 1 and d['request_count'] >= 2" \
  "$API/session"
sess_check "tour can be completed" \
  "d['tour_completed'] is True" \
  -X POST -H 'Content-Type: application/json' -d '{"completed":true}' "$API/session/tour"
sess_check "preferences merge" \
  "d['preferences'].get('lastPage') == '/performance'" \
  -X PATCH -H 'Content-Type: application/json' -d '{"patch":{"lastPage":"/performance"}}' "$API/session/preferences"
rm -f "$CJ"

echo
echo "== $pass passed, $fail failed =="
exit $(( fail > 0 ? 1 : 0 ))
