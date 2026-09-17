"""Route test for GET /markets/snapshot (service mocked)."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi.testclient import TestClient

import main
import markets_service as ms
from auth.conn import get_conn
from auth.dependencies import get_current_user
from db import init_schema
from settings_store import init_settings, set_value

_PREMIUM_USER = {
    "id": 1,
    "email": "premium@test.local",
    "tier": "premium",
    "audience": "base",
    "household_id": None,
    "is_admin": False,
}
_FREE_USER = {
    "id": 2,
    "email": "free@test.local",
    "tier": "free",
    "audience": "base",
    "household_id": None,
    "is_admin": False,
}


def _override_user(user):
    # FOR-D01: /markets/snapshot now gates on markets.sentiment (tier=premium) via
    # require_feature() — gate on an isolated in-memory DB with gating explicitly
    # enabled, mirroring test_whatif_route.py, since the real dev DB may have
    # premium_gating_enabled=false (demo mode) and hide the 402 case.
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    init_settings(conn)
    set_value(conn, "premium_gating_enabled", "true")
    main.app.dependency_overrides[get_conn] = lambda: conn
    main.app.dependency_overrides[get_current_user] = lambda: user


def _clear_user_override():
    main.app.dependency_overrides.pop(get_current_user, None)
    main.app.dependency_overrides.pop(get_conn, None)


async def _fake_snapshot(
    symbol: str, asset_class: str, *, cookie: str | None = None, stepup_tsumi: str | None = None
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "asset_class": asset_class,
        "rating": {"label": "buy", "score": 0.42},
        "sentiment": {"sentiment": "positive"},
        "movers": [{"symbol": "ETHUSDT", "change_pct": 5.0}],
        "degraded": False,
        "disclaimer": ms.DISCLAIMER,
        "_cookie_seen": cookie,
        "_stepup_tsumi_seen": stepup_tsumi,
    }


def test_snapshot_route_returns_aggregate(monkeypatch):
    monkeypatch.setattr(main.markets_service, "fetch_snapshot", _fake_snapshot)
    _override_user(_PREMIUM_USER)
    try:
        client = TestClient(main.app)
        resp = client.get(
            "/markets/snapshot", params={"symbol": "BTCUSDT", "asset_class": "crypto"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "BTCUSDT"
        assert body["rating"]["label"] == "buy"
        assert body["movers"][0]["symbol"] == "ETHUSDT"
        assert body["degraded"] is False
        assert body["disclaimer"]
    finally:
        _clear_user_override()


def test_snapshot_route_defaults_asset_class(monkeypatch):
    monkeypatch.setattr(main.markets_service, "fetch_snapshot", _fake_snapshot)
    _override_user(_PREMIUM_USER)
    try:
        client = TestClient(main.app)
        resp = client.get("/markets/snapshot", params={"symbol": "AAPL.US"})
        assert resp.status_code == 200
        assert resp.json()["asset_class"] == "crypto"  # default
    finally:
        _clear_user_override()


def test_snapshot_route_forwards_cookie(monkeypatch):
    monkeypatch.setattr(main.markets_service, "fetch_snapshot", _fake_snapshot)
    _override_user(_PREMIUM_USER)
    try:
        client = TestClient(main.app)
        resp = client.get(
            "/markets/snapshot",
            params={"symbol": "BTCUSDT"},
            cookies={"suite_session": "tok-99", "stepup_tsumi": "su-99"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["_cookie_seen"] == "tok-99"
        # foroba#206: stepup_tsumi must be forwarded, since Tsumi's require_auth
        # (foroba#199) rejects requests carrying only suite_session with a 428.
        assert body["_stepup_tsumi_seen"] == "su-99"
    finally:
        _clear_user_override()


def test_snapshot_route_requires_premium_for_sentiment(monkeypatch):
    """FOR-D01: a free-tier account must not be able to reach the sentiment-bearing
    snapshot route at all — it is gated server-side on markets.sentiment (tier=premium)."""
    monkeypatch.setattr(main.markets_service, "fetch_snapshot", _fake_snapshot)
    _override_user(_FREE_USER)
    try:
        client = TestClient(main.app)
        resp = client.get("/markets/snapshot", params={"symbol": "BTCUSDT"})
        assert resp.status_code == 402
    finally:
        _clear_user_override()


def test_snapshot_route_anonymous_rejected(monkeypatch):
    """FOR-D01: the route must require auth at all — previously it had none."""
    monkeypatch.setattr(main.markets_service, "fetch_snapshot", _fake_snapshot)
    client = TestClient(main.app)
    resp = client.get("/markets/snapshot", params={"symbol": "BTCUSDT"})
    assert resp.status_code == 401


async def _fake_overview(
    asset_class: str, *, cookie: str | None = None, stepup_tsumi: str | None = None
) -> dict[str, Any]:
    return {
        "asset_class": asset_class,
        "gainers": [{"symbol": "BTCUSDT", "change_pct": 12.0}],
        "losers": [{"symbol": "ETHUSDT", "change_pct": -8.0}],
        "news": {"symbol": "BTCUSDT", "items": [{"title": "Bitcoin rallies"}]},
        "degraded": False,
        "disclaimer": ms.DISCLAIMER,
        "_cookie_seen": cookie,
        "_stepup_tsumi_seen": stepup_tsumi,
    }


def test_overview_route_returns_aggregate(monkeypatch):
    monkeypatch.setattr(main.markets_service, "fetch_overview", _fake_overview)
    client = TestClient(main.app)
    resp = client.get("/markets/overview", params={"asset_class": "crypto"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["asset_class"] == "crypto"
    assert body["gainers"][0]["symbol"] == "BTCUSDT"
    assert body["losers"][0]["symbol"] == "ETHUSDT"
    assert body["news"]["items"][0]["title"] == "Bitcoin rallies"
    assert body["degraded"] is False


def test_overview_route_defaults_asset_class(monkeypatch):
    monkeypatch.setattr(main.markets_service, "fetch_overview", _fake_overview)
    client = TestClient(main.app)
    resp = client.get("/markets/overview")
    assert resp.status_code == 200
    assert resp.json()["asset_class"] == "crypto"


def test_overview_route_forwards_cookie(monkeypatch):
    monkeypatch.setattr(main.markets_service, "fetch_overview", _fake_overview)
    client = TestClient(main.app)
    resp = client.get(
        "/markets/overview",
        params={"asset_class": "crypto"},
        cookies={"suite_session": "tok-99", "stepup_tsumi": "su-99"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["_cookie_seen"] == "tok-99"
    assert body["_stepup_tsumi_seen"] == "su-99"
