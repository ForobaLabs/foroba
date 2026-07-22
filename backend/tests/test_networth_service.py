"""Unit tests for networth_service.py's merge/fold logic — TI-D item 3 Plan 3,
foroba#164. HTTP calls mocked via monkeypatch, no real network access."""
from __future__ import annotations

import pytest

import networth_service as ns


def test_merge_history_two_way_unchanged_when_no_manual_assets():
    bank_history = [
        {"date": "2026-07-20", "balance_cents": 10000},
        {"date": "2026-07-21", "balance_cents": 10500},
    ]
    investments_history = [{"date": "2026-07-20", "value": 50.0}]

    result = ns._merge_history(bank_history, investments_history, [])
    assert result == [
        {"date": "2026-07-20", "bank_eur": 100.0, "investments_eur": 50.0,
         "manual_assets_eur": 0.0, "total_eur": 150.0},
        {"date": "2026-07-21", "bank_eur": 105.0, "investments_eur": 50.0,
         "manual_assets_eur": 0.0, "total_eur": 155.0},
    ]


def test_merge_history_three_way_folds_manual_assets():
    bank_history = [
        {"date": "2026-07-20", "balance_cents": 10000},
        {"date": "2026-07-21", "balance_cents": 10000},
    ]
    investments_history = [{"date": "2026-07-20", "value": 50.0}]
    manual_assets_history = [
        {"date": "2026-07-20", "value_eur": 200.0},
        {"date": "2026-07-21", "value_eur": 250.0},
    ]

    result = ns._merge_history(bank_history, investments_history, manual_assets_history)
    assert result[0]["manual_assets_eur"] == 200.0
    assert result[0]["total_eur"] == 350.0
    assert result[1]["manual_assets_eur"] == 250.0
    assert result[1]["total_eur"] == 400.0


@pytest.mark.asyncio
async def test_fetch_networth_does_not_double_count_manual_assets_in_total(monkeypatch):
    async def _fake_get_json(client, url, params, cookie):
        if "accounts/net-worth" in url:
            return {
                "summary": {"total_cents": 10000, "currency": "EUR", "account_count": 1},
                "history": [{"date": "2026-07-21", "balance_cents": 10000}],
            }
        if "portfolio/summary" in url:
            # Tsumi's total_eur already folds in manual_assets_eur (tsumi#177,
            # confirmed via portfolio_service.py: total_eur = positions + manual_assets_eur).
            return {"total_eur": 250.0, "manual_assets_eur": 200.0, "pnl_eur": 5.0,
                    "pnl_pct": 11.11, "position_count": 2}
        if "portfolio/history" in url:
            return [{"date": "2026-07-21", "value": 50.0}]
        if "manual-assets/net-worth-history" in url:
            return [{"date": "2026-07-21", "value_eur": 200.0}]
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(ns, "_get_json", _fake_get_json)
    result = await ns.fetch_networth(days=30, include_manual_assets=True)

    assert result["total_eur"] == 350.0
    assert result["degraded"] is False


@pytest.mark.asyncio
async def test_fetch_networth_excludes_manual_assets_when_flag_false(monkeypatch):
    call_urls = []

    async def _fake_get_json(client, url, params, cookie):
        call_urls.append(url)
        if "accounts/net-worth" in url:
            return {"summary": {"total_cents": 10000, "currency": "EUR", "account_count": 1},
                    "history": []}
        if "portfolio/summary" in url:
            return {"total_eur": 250.0, "manual_assets_eur": 200.0, "pnl_eur": 5.0,
                    "pnl_pct": 11.11, "position_count": 2}
        if "portfolio/history" in url:
            return []
        raise AssertionError(f"unexpected URL {url} when include_manual_assets=False")

    monkeypatch.setattr(ns, "_get_json", _fake_get_json)
    result = await ns.fetch_networth(days=30, include_manual_assets=False)

    assert result["total_eur"] == 350.0
    assert not any("manual-assets" in u for u in call_urls)
