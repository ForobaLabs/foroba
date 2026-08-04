"""Route test for GET /networth/summary (service mocked, foroba#157)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

import networth_service as ns
from auth.dependencies import get_current_user
from main import app


async def _fake_fetch_networth(
    days: int,
    *,
    cookie: str | None = None,
    stepup_pazuru: str | None = None,
    stepup_tsumi: str | None = None,
    include_manual_assets: bool = True,
    include_debts: bool = False,
) -> dict[str, Any]:
    return {
        "bank": {
            "total_cents": 10000,
            "currency": "EUR",
            "account_count": 1,
            "excluded_accounts": [],
        },
        "investments": {"total_eur": 50.0, "pnl_eur": 5.0, "pnl_pct": 11.11, "position_count": 2},
        "total_eur": 150.0,
        "history": [
            {
                "date": "2026-07-16",
                "bank_eur": 100.0,
                "investments_eur": 50.0,
                "manual_assets_eur": 0.0,
                "total_eur": 150.0,
            }
        ],
        "degraded": False,
        "disclaimer": ns.DISCLAIMER,
        "_cookie_seen": cookie,
        "_stepup_pazuru_seen": stepup_pazuru,
        "_stepup_tsumi_seen": stepup_tsumi,
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
        resp = client.get(
            "/networth/summary",
            cookies={"suite_session": "tok-99", "stepup_pazuru": "sp-99", "stepup_tsumi": "st-99"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["_cookie_seen"] == "tok-99"
        # foroba#206: both per-app stepup cookies must be forwarded.
        assert body["_stepup_pazuru_seen"] == "sp-99"
        assert body["_stepup_tsumi_seen"] == "st-99"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_networth_route_forwards_include_manual_assets_flag(monkeypatch):
    captured = {}

    async def _capturing_fetch(
        days, *, cookie=None, include_manual_assets=True, include_debts=False, **_
    ):
        captured["include_manual_assets"] = include_manual_assets
        return await _fake_fetch_networth(days, cookie=cookie)

    monkeypatch.setattr(ns, "fetch_networth", _capturing_fetch)
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "u1@test.local"}
    try:
        client = TestClient(app)
        resp = client.get("/networth/summary?include_manual_assets=false")
        assert resp.status_code == 200
        assert captured["include_manual_assets"] is False
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_networth_route_forwards_include_debts_flag(monkeypatch):
    captured = {}

    async def _capturing_fetch(
        days, *, cookie=None, include_manual_assets=True, include_debts=False, **_
    ):
        captured["include_debts"] = include_debts
        return await _fake_fetch_networth(days, cookie=cookie)

    monkeypatch.setattr(ns, "fetch_networth", _capturing_fetch)
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "u1@test.local"}
    try:
        client = TestClient(app)
        resp = client.get("/networth/summary?include_debts=true")
        assert resp.status_code == 200
        assert captured["include_debts"] is True
    finally:
        app.dependency_overrides.pop(get_current_user, None)
