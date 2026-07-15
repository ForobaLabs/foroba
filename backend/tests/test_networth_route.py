"""Route test for GET /networth/summary (service mocked, foroba#157)."""
from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from auth.dependencies import get_current_user
from main import app
import networth_service as ns


async def _fake_fetch_networth(days: int, *, cookie: str | None = None) -> dict[str, Any]:
    return {
        "bank": {"total_cents": 10000, "currency": "EUR", "account_count": 1, "excluded_accounts": []},
        "investments": {"total_eur": 50.0, "pnl_eur": 5.0, "pnl_pct": 11.11, "position_count": 2},
        "total_eur": 150.0,
        "history": [{"date": "2026-07-16", "bank_eur": 100.0, "investments_eur": 50.0, "total_eur": 150.0}],
        "degraded": False,
        "disclaimer": ns.DISCLAIMER,
        "_cookie_seen": cookie,
    }


def test_networth_route_requires_auth():
    client = TestClient(app)
    resp = client.get("/networth/summary")
    assert resp.status_code in (401, 403)


def test_networth_route_returns_aggregate(monkeypatch):
    monkeypatch.setattr(ns, "fetch_networth", _fake_fetch_networth)
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "u1@test.local"}
    try:
        client = TestClient(app)
        resp = client.get("/networth/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_eur"] == 150.0
        assert body["bank"]["total_cents"] == 10000
        assert body["investments"]["total_eur"] == 50.0
        assert body["degraded"] is False
        assert body["disclaimer"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_networth_route_forwards_cookie(monkeypatch):
    monkeypatch.setattr(ns, "fetch_networth", _fake_fetch_networth)
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "u1@test.local"}
    try:
        client = TestClient(app)
        resp = client.get("/networth/summary", cookies={"suite_session": "tok-99"})
        assert resp.status_code == 200
        assert resp.json()["_cookie_seen"] == "tok-99"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
