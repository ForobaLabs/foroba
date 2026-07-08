"""Route test for GET /markets/snapshot (service mocked)."""
from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

import main
import markets_service as ms


async def _fake_snapshot(symbol: str, asset_class: str, *, cookie: str | None = None) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "asset_class": asset_class,
        "rating": {"label": "buy", "score": 0.42},
        "sentiment": {"sentiment": "positive"},
        "movers": [{"symbol": "ETHUSDT", "change_pct": 5.0}],
        "degraded": False,
        "disclaimer": ms.DISCLAIMER,
        "_cookie_seen": cookie,
    }


def test_snapshot_route_returns_aggregate(monkeypatch):
    monkeypatch.setattr(main.markets_service, "fetch_snapshot", _fake_snapshot)
    client = TestClient(main.app)
    resp = client.get("/markets/snapshot", params={"symbol": "BTCUSDT", "asset_class": "crypto"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "BTCUSDT"
    assert body["rating"]["label"] == "buy"
    assert body["movers"][0]["symbol"] == "ETHUSDT"
    assert body["degraded"] is False
    assert body["disclaimer"]


def test_snapshot_route_defaults_asset_class(monkeypatch):
    monkeypatch.setattr(main.markets_service, "fetch_snapshot", _fake_snapshot)
    client = TestClient(main.app)
    resp = client.get("/markets/snapshot", params={"symbol": "AAPL.US"})
    assert resp.status_code == 200
    assert resp.json()["asset_class"] == "crypto"  # default


def test_snapshot_route_forwards_cookie(monkeypatch):
    monkeypatch.setattr(main.markets_service, "fetch_snapshot", _fake_snapshot)
    client = TestClient(main.app)
    resp = client.get(
        "/markets/snapshot",
        params={"symbol": "BTCUSDT"},
        cookies={"suite_session": "tok-99"},
    )
    assert resp.status_code == 200
    assert resp.json()["_cookie_seen"] == "tok-99"


async def _fake_overview(asset_class: str, *, cookie: str | None = None) -> dict[str, Any]:
    return {
        "asset_class": asset_class,
        "gainers": [{"symbol": "BTCUSDT", "change_pct": 12.0}],
        "losers": [{"symbol": "ETHUSDT", "change_pct": -8.0}],
        "news": {"symbol": "BTCUSDT", "items": [{"title": "Bitcoin rallies"}]},
        "degraded": False,
        "disclaimer": ms.DISCLAIMER,
        "_cookie_seen": cookie,
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
        cookies={"suite_session": "tok-99"},
    )
    assert resp.status_code == 200
    assert resp.json()["_cookie_seen"] == "tok-99"
