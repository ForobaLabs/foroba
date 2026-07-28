"""Tests for the Markets aggregation service (Tsumi HTTP boundary mocked)."""
from __future__ import annotations

import asyncio
from typing import Any

import markets_service as ms


class _FakeResponse:
    def __init__(self, payload: dict[str, Any], status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeClient:
    """Stand-in for httpx.AsyncClient; routes by URL substring."""

    def __init__(self, routes: dict[str, Any]) -> None:
        self._routes = routes

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        for needle, value in self._routes.items():
            if needle in url:
                if isinstance(value, Exception):
                    raise value
                return _FakeResponse(value)
        raise RuntimeError(f"unrouted url: {url}")


_COMBINED = {"symbol": "BTCUSDT", "consensus": {"label": "buy", "score": 0.42}}
_SENTIMENT = {"symbol": "BTCUSDT", "sentiment": "positive", "headlines": []}
_SCAN = {"screen": "top_movers", "results": [{"symbol": "ETHUSDT", "change_pct": 5.0}]}


def _client_factory(routes):
    def _factory(*args, **kwargs):
        return _FakeClient(routes)

    return _factory


def test_fetch_snapshot_assembles_all_sections(monkeypatch):
    monkeypatch.setattr(
        ms.httpx,
        "AsyncClient",
        _client_factory(
            {"combined": _COMBINED, "news/sentiment": _SENTIMENT, "screener/scan": _SCAN}
        ),
    )
    snap = asyncio.run(ms.fetch_snapshot("BTCUSDT", "crypto"))
    assert snap["symbol"] == "BTCUSDT"
    assert snap["asset_class"] == "crypto"
    assert snap["rating"] == _COMBINED["consensus"]
    assert snap["sentiment"]["sentiment"] == "positive"
    assert snap["movers"][0]["symbol"] == "ETHUSDT"
    assert snap["degraded"] is False
    assert snap["disclaimer"]


def test_fetch_snapshot_degrades_on_one_failure(monkeypatch):
    monkeypatch.setattr(
        ms.httpx,
        "AsyncClient",
        _client_factory(
            {
                "combined": _COMBINED,
                "news/sentiment": RuntimeError("tsumi down"),
                "screener/scan": _SCAN,
            }
        ),
    )
    snap = asyncio.run(ms.fetch_snapshot("BTCUSDT", "crypto"))
    assert snap["rating"] == _COMBINED["consensus"]
    assert snap["sentiment"] is None
    assert snap["movers"][0]["symbol"] == "ETHUSDT"
    assert snap["degraded"] is True


def test_fetch_snapshot_all_down_returns_partial_not_raise(monkeypatch):
    boom = RuntimeError("network down")
    monkeypatch.setattr(
        ms.httpx,
        "AsyncClient",
        _client_factory(
            {"combined": boom, "news/sentiment": boom, "screener/scan": boom}
        ),
    )
    snap = asyncio.run(ms.fetch_snapshot("BTCUSDT", "crypto"))
    assert snap["rating"] is None
    assert snap["sentiment"] is None
    assert snap["movers"] is None
    assert snap["degraded"] is True
    assert snap["disclaimer"]


def test_fetch_snapshot_forwards_cookie(monkeypatch):
    seen: dict[str, Any] = {}

    class _RecordingClient(_FakeClient):
        async def get(self, url: str, **kwargs: Any) -> _FakeResponse:
            seen.setdefault("cookies", kwargs.get("cookies"))
            return await super().get(url, **kwargs)

    def _factory(*args, **kwargs):
        return _RecordingClient(
            {"combined": _COMBINED, "news/sentiment": _SENTIMENT, "screener/scan": _SCAN}
        )

    monkeypatch.setattr(ms.httpx, "AsyncClient", _factory)
    asyncio.run(ms.fetch_snapshot("BTCUSDT", "crypto", cookie="abc123"))
    assert seen["cookies"] == {"suite_session": "abc123"}


_MOVERS = {
    "asset_class": "crypto",
    "gainers": [{"symbol": "BTCUSDT", "change_pct": 12.0}],
    "losers": [{"symbol": "ETHUSDT", "change_pct": -8.0}],
}
_HEADLINES = {"symbol": "BTCUSDT", "items": [{"title": "Bitcoin rallies", "source": "yahoo"}]}


def test_fetch_overview_assembles_gainers_losers_and_news(monkeypatch):
    monkeypatch.setattr(
        ms.httpx,
        "AsyncClient",
        _client_factory({"screener/movers": _MOVERS, "news/headlines": _HEADLINES}),
    )
    overview = asyncio.run(ms.fetch_overview("crypto"))
    assert overview["asset_class"] == "crypto"
    assert overview["gainers"][0]["symbol"] == "BTCUSDT"
    assert overview["losers"][0]["symbol"] == "ETHUSDT"
    assert overview["news"]["items"][0]["title"] == "Bitcoin rallies"
    assert overview["degraded"] is False
    assert overview["disclaimer"]


def test_fetch_overview_degrades_when_movers_fail(monkeypatch):
    monkeypatch.setattr(
        ms.httpx,
        "AsyncClient",
        _client_factory({"screener/movers": RuntimeError("tsumi down")}),
    )
    overview = asyncio.run(ms.fetch_overview("crypto"))
    assert overview["gainers"] is None
    assert overview["losers"] is None
    assert overview["degraded"] is True


def test_fetch_overview_no_gainers_skips_news(monkeypatch):
    empty_movers = {
        "asset_class": "equity",
        "gainers": [],
        "losers": [{"symbol": "ETHUSDT", "change_pct": -8.0}],
    }
    monkeypatch.setattr(
        ms.httpx,
        "AsyncClient",
        _client_factory({"screener/movers": empty_movers, "news/headlines": _HEADLINES}),
    )
    overview = asyncio.run(ms.fetch_overview("equity"))
    assert overview["gainers"] == []
    assert overview["news"] is None
    assert overview["degraded"] is True
