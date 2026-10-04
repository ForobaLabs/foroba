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
        {
            "date": "2026-07-20",
            "bank_eur": 100.0,
            "investments_eur": 50.0,
            "manual_assets_eur": 0.0,
            "total_eur": 150.0,
        },
        {
            "date": "2026-07-21",
            "bank_eur": 105.0,
            "investments_eur": 50.0,
            "manual_assets_eur": 0.0,
            "total_eur": 155.0,
        },
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
            return {
                "total_eur": 250.0,
                "manual_assets_eur": 200.0,
                "pnl_eur": 5.0,
                "pnl_pct": 11.11,
                "position_count": 2,
            }
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
            return {
                "summary": {"total_cents": 10000, "currency": "EUR", "account_count": 1},
                "history": [],
            }
        if "portfolio/summary" in url:
            return {
                "total_eur": 250.0,
                "manual_assets_eur": 200.0,
                "pnl_eur": 5.0,
                "pnl_pct": 11.11,
                "position_count": 2,
            }
        if "portfolio/history" in url:
            return []
        raise AssertionError(f"unexpected URL {url} when include_manual_assets=False")

    monkeypatch.setattr(ns, "_get_json", _fake_get_json)
    result = await ns.fetch_networth(days=30, include_manual_assets=False)

    assert result["total_eur"] == 350.0
    assert not any("manual-assets" in u for u in call_urls)


@pytest.mark.asyncio
async def test_fetch_networth_subtracts_debts_when_include_debts_true(monkeypatch):
    async def _fake_get_json(client, url, params, cookie):
        if "accounts/net-worth" in url:
            return {
                "summary": {"total_cents": 1_000_000, "currency": "EUR", "account_count": 1},
                "history": [],
            }
        if "portfolio/summary" in url:
            return {
                "total_eur": 0.0,
                "manual_assets_eur": 0.0,
                "pnl_eur": 0.0,
                "pnl_pct": 0.0,
                "position_count": 0,
            }
        if "portfolio/history" in url:
            return []
        if "debts/net-worth" in url:
            return {"total_debt_cents": 50_000, "currency": "EUR"}
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(ns, "_get_json", _fake_get_json)
    result = await ns.fetch_networth(days=30, include_manual_assets=False, include_debts=True)

    assert result["debts_eur"] == 500.0
    assert result["total_eur"] == 9_500.0


@pytest.mark.asyncio
async def test_fetch_networth_omits_debts_key_when_include_debts_false(monkeypatch):
    call_urls = []

    async def _fake_get_json(client, url, params, cookie):
        call_urls.append(url)
        if "accounts/net-worth" in url:
            return {
                "summary": {"total_cents": 1_000_000, "currency": "EUR", "account_count": 1},
                "history": [],
            }
        if "portfolio/summary" in url:
            return {
                "total_eur": 0.0,
                "manual_assets_eur": 0.0,
                "pnl_eur": 0.0,
                "pnl_pct": 0.0,
                "position_count": 0,
            }
        if "portfolio/history" in url:
            return []
        raise AssertionError(f"unexpected URL {url} when include_debts=False")

    monkeypatch.setattr(ns, "_get_json", _fake_get_json)
    result = await ns.fetch_networth(days=30, include_manual_assets=False, include_debts=False)

    assert "debts_eur" not in result
    assert result["total_eur"] == 10_000.0
    assert not any("debts" in u for u in call_urls)


def test_import_events_filters_and_labels():
    entries = [
        {"filename": "jan.csv", "destination": "account", "imported_count": 5, "undone": False,
         "created_at": "2026-01-05T10:00:00"},
        {"filename": "undone.csv", "destination": "account", "imported_count": 5, "undone": True,
         "created_at": "2026-02-01T10:00:00"},
        {"filename": "empty.csv", "destination": "account", "imported_count": 0, "undone": False,
         "created_at": "2026-02-02T10:00:00"},
        {"filename": "assets.csv", "destination": "manual_assets", "imported_count": 3,
         "undone": False, "created_at": "2026-02-03T10:00:00"},
        {"filename": "bad", "destination": "account", "imported_count": 1, "undone": False,
         "created_at": "oops"},
    ]
    assert ns._import_events(entries) == [
        {"date": "2026-01-05", "label": "jan.csv", "kind": "import"}
    ]
    assert ns._import_events(None) == []


def test_import_events_capped_to_newest_12():
    entries = [
        {"filename": f"f{i}.csv", "destination": "account", "imported_count": 1, "undone": False,
         "created_at": f"2026-01-{i:02d}T00:00:00"}
        for i in range(1, 21)
    ]
    out = ns._import_events(entries)
    assert len(out) == 12
    assert out[0]["date"] == "2026-01-09" and out[-1]["date"] == "2026-01-20"


@pytest.mark.asyncio
async def test_fetch_networth_includes_events_and_survives_log_failure(monkeypatch):
    log_state = {"fail": False}

    async def _fake_get_json(client, url, params, cookie):
        if "accounts/net-worth" in url:
            return {
                "summary": {"total_cents": 10000, "currency": "EUR", "account_count": 1},
                "history": [],
            }
        if "portfolio/summary" in url:
            return {"total_eur": 0.0, "manual_assets_eur": 0.0, "pnl_eur": 0.0,
                    "pnl_pct": 0.0, "position_count": 0}
        if "portfolio/history" in url:
            return []
        if "import/log" in url:
            if log_state["fail"]:
                return None  # _get_json's failure contract (e.g. 428)
            return [{"filename": "a.csv", "destination": "account", "imported_count": 2,
                     "undone": False, "created_at": "2026-03-01T00:00:00"}]
        raise AssertionError(url)

    monkeypatch.setattr(ns, "_get_json", _fake_get_json)
    ok = await ns.fetch_networth(days=30, include_manual_assets=False)
    assert ok["events"] == [{"date": "2026-03-01", "label": "a.csv", "kind": "import"}]
    assert ok["degraded"] is False

    log_state["fail"] = True
    bad = await ns.fetch_networth(days=30, include_manual_assets=False)
    assert bad["events"] == []
    assert bad["degraded"] is False
