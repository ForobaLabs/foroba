"""Route tests for /reports/monthly/* (service mocked, foroba#159, TI-D item 2)."""
from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

import db
import monthly_report_service as mrs
from auth.conn import get_conn
from auth.dependencies import get_current_user
from db import init_schema
from main import app
from settings_store import init_settings, set_value

_PREMIUM_USER = {"id": 1, "email": "u1@test.local", "name": "U1", "tier": "premium",
                  "audience": "base", "household_id": None, "is_admin": False}
_FREE_USER = {"id": 2, "email": "u2@test.local", "name": "U2", "tier": "free",
              "audience": "base", "household_id": None, "is_admin": False}


def _override_user(user):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    init_settings(conn)
    set_value(conn, "premium_gating_enabled", "true")
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: user
    return conn


def _teardown():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_conn, None)


def test_generate_requires_premium():
    _override_user(_FREE_USER)
    try:
        client = TestClient(app)
        resp = client.post("/reports/monthly/generate", json={"year_month": "2026-07"})
        assert resp.status_code == 402
    finally:
        _teardown()


def test_generate_returns_report(monkeypatch):
    conn = _override_user(_PREMIUM_USER)

    async def fake_generate(conn_, user, year_month, trigger, *, cookie):
        return db.create_monthly_report(conn_, user_id=user["id"], year_month=year_month, trigger=trigger)

    monkeypatch.setattr(mrs, "generate_new_report", fake_generate)
    try:
        client = TestClient(app)
        resp = client.post("/reports/monthly/generate", json={"year_month": "2026-07"})
        assert resp.status_code == 200
        assert resp.json()["year_month"] == "2026-07"
    finally:
        _teardown()


def test_generate_returns_429_on_quota_exceeded(monkeypatch):
    _override_user(_PREMIUM_USER)

    async def fake_generate(conn_, user, year_month, trigger, *, cookie):
        raise mrs.QuotaExceededError(6)

    monkeypatch.setattr(mrs, "generate_new_report", fake_generate)
    try:
        client = TestClient(app)
        resp = client.post("/reports/monthly/generate", json={"year_month": "2026-07"})
        assert resp.status_code == 429
    finally:
        _teardown()


def test_retry_returns_409_on_invalid_retry(monkeypatch):
    _override_user(_PREMIUM_USER)

    async def fake_retry(conn_, user, report_id, *, cookie):
        raise mrs.InvalidRetryError("success")

    monkeypatch.setattr(mrs, "retry_report", fake_retry)
    try:
        client = TestClient(app)
        resp = client.post("/reports/monthly/1/retry")
        assert resp.status_code == 409
    finally:
        _teardown()


def test_pdf_returns_200_for_success_row():
    conn = _override_user(_PREMIUM_USER)
    row = db.create_monthly_report(conn, user_id=_PREMIUM_USER["id"], year_month="2026-07", trigger="manual")
    db.update_monthly_report_result(
        conn, row["id"], status="success", narrative_text="Great month.",
        context_snapshot_json=None, error_message=None, attempt_count=1,
    )
    try:
        client = TestClient(app)
        resp = client.get(f"/reports/monthly/{row['id']}/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
    finally:
        _teardown()


def test_pdf_returns_409_for_non_success_row():
    conn = _override_user(_PREMIUM_USER)
    row = db.create_monthly_report(conn, user_id=_PREMIUM_USER["id"], year_month="2026-07", trigger="manual")
    try:
        client = TestClient(app)
        resp = client.get(f"/reports/monthly/{row['id']}/pdf")
        assert resp.status_code == 409
    finally:
        _teardown()
