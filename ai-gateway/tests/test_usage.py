from datetime import UTC, datetime

import pytest

import db
import usage
from auth import Caller

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
U7 = Caller(user_id=7, tier="free", is_admin=False)


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr(usage, "now", lambda: NOW)


def _rec(conn, caller, neurons, outcome="ok", at="2026-10-05T10:00:00+00:00", **kw):
    usage.record(
        conn, caller, kw.get("app", "pazuru"), kw.get("feature", "chat"), "chat",
        "cloudflare", kw.get("model", "m1"), neurons, 12, outcome, at=at,
    )


def test_usage_endpoint_percent(api):
    _rec(db.connect(), U7, 5000)
    body = api("GET", "/v1/usage", user=7, tier="free").json()
    assert body == {
        "tier": "free", "allowance": 20000, "used": 5000, "percent": 25, "unlimited": False,
    }


def test_usage_only_counts_current_month_and_caller(api):
    conn = db.connect()
    _rec(conn, U7, 4000, at="2026-09-30T23:59:00+00:00")
    _rec(conn, Caller(8, "free", False), 9000)
    assert api("GET", "/v1/usage").json()["used"] == 0


def test_usage_unlimited_for_allowlisted(api, monkeypatch):
    monkeypatch.setenv("AI_TEST_ALLOWLIST", "7")
    _rec(db.connect(), U7, 50000)
    body = api("GET", "/v1/usage").json()
    assert body["unlimited"] is True and body["percent"] == 0


def test_admin_usage_403_for_non_admin(api):
    assert api("GET", "/v1/admin/usage?month=2026-10").status_code == 403


def test_admin_usage_aggregates(api):
    conn = db.connect()
    _rec(conn, U7, 100)
    _rec(conn, U7, 50, model="m2", feature="jeli")
    _rec(conn, Caller(8, "premium", False), 300, outcome="partial")
    body = api("GET", "/v1/admin/usage?month=2026-10", admin=True).json()
    assert body["totals"] == {"neurons": 450, "requests": 3, "users": 2}
    assert body["by_user"][0] == {"user_id": 8, "tier": "premium", "neurons": 300, "requests": 1}
    assert {m["model"] for m in body["by_model"]} == {"m1", "m2"}
    assert body["outcomes"] == {"ok": 2, "partial": 1}
    assert api("GET", "/v1/admin/usage?month=bad", admin=True).status_code == 422


def test_ledger_row_has_no_prompt_text():
    conn = db.connect()
    _rec(conn, U7, 10)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(ai_usage)")}
    assert cols == {
        "id", "user_id", "tier", "app", "feature", "task", "provider", "model",
        "neurons", "latency_ms", "outcome", "at",
    }
