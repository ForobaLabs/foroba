"""Tests for the pure what-if projection engine (foroba#162)."""
from __future__ import annotations

import whatif_service as ws


def test_projection_monthly_resolution_for_first_24_months():
    points = ws.compute_projection(
        horizon_months=24, bank_total_cents=100_000, investments_total_eur=0.0,
        monthly_net_delta_cents=0, spend_cut_savings_cents=0, income_delta_cents=0,
        one_off_events=[], investment_growth_rate_pct=0.0,
    )
    assert len(points) == 24
    assert all(p["resolution"] == "monthly" for p in points)
    assert [p["month"] for p in points] == list(range(1, 25))


def test_projection_quarterly_resolution_between_25_and_60():
    points = ws.compute_projection(
        horizon_months=60, bank_total_cents=0, investments_total_eur=0.0,
        monthly_net_delta_cents=0, spend_cut_savings_cents=0, income_delta_cents=0,
        one_off_events=[], investment_growth_rate_pct=0.0,
    )
    quarterly = [p for p in points if p["resolution"] == "quarterly"]
    assert [p["month"] for p in quarterly] == [27, 30, 33, 36, 39, 42, 45, 48, 51, 54, 57, 60]


def test_projection_yearly_resolution_beyond_60_and_includes_final_month():
    points = ws.compute_projection(
        horizon_months=100, bank_total_cents=0, investments_total_eur=0.0,
        monthly_net_delta_cents=0, spend_cut_savings_cents=0, income_delta_cents=0,
        one_off_events=[], investment_growth_rate_pct=0.0,
    )
    yearly = [p for p in points if p["resolution"] == "yearly"]
    assert yearly[-1]["month"] == 100  # final partial year still emitted
    assert [p["month"] for p in yearly[:-1]] == [72, 84, 96]


def test_projection_applies_monthly_net_delta_and_savings_and_income():
    points = ws.compute_projection(
        horizon_months=1, bank_total_cents=100_000, investments_total_eur=0.0,
        monthly_net_delta_cents=10_000, spend_cut_savings_cents=5_000,
        income_delta_cents=2_000, one_off_events=[], investment_growth_rate_pct=0.0,
    )
    # 100000 + 10000 + 5000 + 2000 = 117000 cents = 1170.00 EUR
    assert points[0]["bank_eur"] == 1170.0


def test_projection_applies_one_off_event_at_correct_month():
    points = ws.compute_projection(
        horizon_months=3, bank_total_cents=0, investments_total_eur=0.0,
        monthly_net_delta_cents=0, spend_cut_savings_cents=0, income_delta_cents=0,
        one_off_events=[{"month_offset": 2, "amount_cents": 50_000, "label": "Bonus"}],
        investment_growth_rate_pct=0.0,
    )
    assert points[0]["bank_eur"] == 0.0
    assert points[1]["bank_eur"] == 500.0
    assert points[2]["bank_eur"] == 500.0  # persists forward


def test_projection_compounds_investments_monthly():
    points = ws.compute_projection(
        horizon_months=12, bank_total_cents=0, investments_total_eur=1000.0,
        monthly_net_delta_cents=0, spend_cut_savings_cents=0, income_delta_cents=0,
        one_off_events=[], investment_growth_rate_pct=12.0,  # 1%/month
    )
    # 1000 * 1.01^12 ≈ 1126.83
    assert abs(points[-1]["investments_eur"] - 1126.83) < 0.5


import pytest


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self):
        pass
    def json(self):
        return self._payload


class _FakeClient:
    """Routes GET/POST to canned payloads by URL suffix, mirroring httpx.AsyncClient."""
    def __init__(self, get_map: dict[str, dict], post_map: dict[str, dict]):
        self._get_map = get_map
        self._post_map = post_map
    async def get(self, url, params=None, cookies=None, timeout=None):
        for suffix, payload in self._get_map.items():
            if url.endswith(suffix):
                return _FakeResponse(payload)
        raise AssertionError(f"unexpected GET {url}")
    async def post(self, url, json=None, cookies=None, timeout=None):
        for suffix, payload in self._post_map.items():
            if url.endswith(suffix):
                return _FakeResponse(payload)
        raise AssertionError(f"unexpected POST {url}")
    async def __aenter__(self):
        return self
    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def fake_ok_client(monkeypatch):
    history = [{"date": f"2026-06-{i:02d}", "balance_cents": 100_000 + i * 100} for i in range(1, 32)]
    client = _FakeClient(
        get_map={
            "/api/accounts/net-worth": {"summary": {"total_cents": 500_000}, "history": history},
            "/api/portfolio/summary": {"total_eur": 200.0},
            "/api/goals": [
                {"id": 1, "name": "House", "target_cents": 1_000_000, "saved_cents": 100_000,
                 "monthly_contribution_cents": 20_000, "deadline": None, "projected_completion": "2027-01-01"},
            ],
        },
        post_map={
            "/api/forecasts/what-if": {"base_cents": 80_000},
            "/api/goals/project": {"months_needed": 30, "projected_date": "2028-01-01", "on_track": None, "required_monthly_to_hit_deadline": None},
        },
    )
    monkeypatch.setattr(ws.httpx, "AsyncClient", lambda: client)
    return client


@pytest.mark.asyncio
async def test_simulate_returns_points_and_disclaimer(fake_ok_client):
    result = await ws.simulate(
        {"eliminate_categories": ["dining"], "goal_contributions": [], "one_off_events": [],
         "income_delta_cents": 0, "investment_growth_rate_pct": 0.0},
        horizon_months=1, owner_cookie=None,
    )
    assert result["degraded"] is False
    assert result["disclaimer"] == ws.DISCLAIMER
    assert len(result["points"]) == 1


@pytest.mark.asyncio
async def test_simulate_degrades_gracefully_when_tsumi_down(monkeypatch):
    history = [{"date": f"2026-06-{i:02d}", "balance_cents": 100_000} for i in range(1, 32)]

    class _FailingTsumiClient(_FakeClient):
        async def get(self, url, params=None, cookies=None, timeout=None):
            if url.endswith("/api/portfolio/summary"):
                raise httpx_mod.ConnectError("down")
            return await super().get(url, params=params, cookies=cookies, timeout=timeout)

    import httpx as httpx_mod
    client = _FailingTsumiClient(
        get_map={
            "/api/accounts/net-worth": {"summary": {"total_cents": 100_000}, "history": history},
            "/api/goals": [],
        },
        post_map={"/api/forecasts/what-if": {"base_cents": 0}},
    )
    monkeypatch.setattr(ws.httpx, "AsyncClient", lambda: client)
    result = await ws.simulate(
        {"goal_contributions": [], "one_off_events": [], "income_delta_cents": 0,
         "investment_growth_rate_pct": 5.0},
        horizon_months=1, owner_cookie=None,
    )
    assert result["degraded"] is True
    assert result["points"][0]["investments_eur"] == 0.0


@pytest.mark.asyncio
async def test_simulate_projects_goal_contribution_override(fake_ok_client):
    result = await ws.simulate(
        {"goal_contributions": [{"goal_id": 1, "extra_monthly_cents": 10_000}],
         "one_off_events": [], "income_delta_cents": 0, "investment_growth_rate_pct": 0.0},
        horizon_months=1, owner_cookie=None,
    )
    assert len(result["goal_impacts"]) == 1
    assert result["goal_impacts"][0]["goal_id"] == 1
    assert result["goal_impacts"][0]["new_projection"]["months_needed"] == 30
