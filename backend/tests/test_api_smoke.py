"""In-process API smoke tests. Skipped automatically without a database.

Run: `docker compose up -d db` then `pytest backend/tests/test_api_smoke.py`.
"""
from __future__ import annotations

import pytest

from .conftest import requires_db

pytestmark = requires_db


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_ready_and_seeded(client):
    body = client.get("/api/ready").json()
    assert body["db"] == "up"
    assert body["seeded"] is True, "database is not seeded -- run db/seed.sql"


def test_dashboard_has_live_numbers(client):
    d = client.get("/api/dashboard/summary").json()
    assert d["kpis"]["total_customers"] > 0
    assert len(d["revenue_trend"]) >= 1
    assert d["segment_performance"], "expected RFM segments"


def test_workspace_runs_catalog_query_with_plan(client):
    r = client.post(
        "/api/workspace/run",
        json={"query_id": "01_revenue_trend", "explain": True},
    ).json()
    assert r["ok"] and r["row_count"] > 0
    assert r["plan"] is not None
    assert r["execution_ms"] is not None


def test_workspace_blocks_writes_and_unlisted_tables(client):
    assert client.post("/api/workspace/run", json={"sql": "DROP TABLE orders"}).json()["ok"] is False
    assert client.post("/api/workspace/run", json={"sql": "SELECT * FROM pg_user"}).json()["ok"] is False


def test_workspace_runs_valid_custom_select(client):
    r = client.post(
        "/api/workspace/run",
        json={"sql": "SELECT count(*) AS n FROM customers", "explain": False},
    ).json()
    assert r["ok"] and r["rows"][0]["n"] > 0


def test_perf_benchmark_returns_real_measurements(client):
    r = client.post(
        "/api/performance/scenarios/index_event_type_time/benchmark", json={}
    ).json()
    c = r["comparison"]
    assert c["execution_ms_before"] is not None
    assert c["execution_ms_after"] is not None


def test_customer_rfm(client):
    r = client.get("/api/customers/rfm").json()
    assert r["ok"] and r["row_count"] > 0


def test_ai_ask_rule_based_path(client):
    r = client.post("/api/ai/ask", json={"question": "What is our repeat purchase rate?"}).json()
    assert r["ok"] and r["sql_valid"]
    assert r["row_count"] >= 1
    assert r["engine"] in {"rule-based", "llm"}


def test_ai_ask_rejects_gibberish(client):
    r = client.post("/api/ai/ask", json={"question": "zxcv qwer asdf hjkl"}).json()
    assert r["ok"] is False


def test_data_quality_checks(client):
    d = client.get("/api/data-quality/checks").json()
    assert d["summary"]["total"] >= 8


def test_recommendations_have_evidence(client):
    d = client.get("/api/recommendations").json()
    assert d["count"] >= 1
    assert all(r["evidence"] for r in d["recommendations"])


# --- session / cookies ------------------------------------------------------
def test_session_cookie_issued_and_persists(client):
    r1 = client.get("/api/session")
    assert r1.status_code == 200
    body = r1.json()
    assert body["is_new"] is True
    assert len(body["session_id"]) >= 16
    assert "xeno_session" in r1.cookies or "xeno_session" in client.cookies

    # second call on the same client reuses the session
    r2 = client.get("/api/session").json()
    assert r2["session_id"] == body["session_id"]
    assert r2["is_new"] is False
    assert r2["request_count"] >= r1.json()["request_count"]


def test_forged_cookie_is_rejected_and_new_session_minted(client):
    forged = client.__class__(client.app)  # fresh client, no cookies
    forged.cookies.set("xeno_session", "not-a-real-id.deadbeef")
    body = forged.get("/api/session").json()
    assert body["is_new"] is True  # bad signature -> ignored, fresh session


def test_workspace_run_is_recorded_in_session_history(client):
    client.get("/api/session")  # ensure a session
    run = client.post(
        "/api/workspace/run",
        json={"query_id": "07_repeat_purchase_rate", "explain": False},
    ).json()
    assert run["ok"]
    hist = client.get("/api/session").json()["recent_queries"]
    assert any(h["source"] == "catalog" and h["ok"] for h in hist)


def test_tour_and_preferences_persist(client):
    client.get("/api/session")
    assert client.post("/api/session/tour", json={"completed": True}).json()["tour_completed"] is True
    prefs = client.patch(
        "/api/session/preferences", json={"patch": {"lastPage": "/ai"}}
    ).json()["preferences"]
    assert prefs.get("lastPage") == "/ai"
    assert client.get("/api/session").json()["tour_completed"] is True
