"""Unit tests for notification_service.py's deterministic alert checks (foroba#158)."""

from __future__ import annotations

import db as db_module
import notification_service as ns


def _conn():
    return db_module.connect(":memory:")


def test_balance_low_fires_below_threshold():
    accounts = [{"id": 1, "display_name": "Checking", "currency": "EUR", "balance_cents": 500}]
    alerts = ns._check_balance_low(accounts, threshold_cents=10000)
    assert len(alerts) == 1
    assert alerts[0]["type"] == "balance_low"
    assert alerts[0]["key"].startswith("balance_low:1:")


def test_balance_low_silent_above_threshold():
    accounts = [{"id": 1, "display_name": "Checking", "currency": "EUR", "balance_cents": 50000}]
    assert ns._check_balance_low(accounts, threshold_cents=10000) == []


def test_goal_reached_only_for_achieved():
    goals = [
        {
            "id": 1,
            "name": "Emergency fund",
            "saved_cents": 100000,
            "currency": "EUR",
            "is_achieved": True,
        },
        {"id": 2, "name": "Car", "saved_cents": 500, "currency": "EUR", "is_achieved": False},
    ]
    alerts = ns._check_goals(goals)
    assert len(alerts) == 1
    assert alerts[0]["key"] == "goal_reached:1"


def test_recurring_increase_fires_after_baseline_established():
    conn = _conn()
    pattern = {"id": 1, "merchant": "Netflix", "amount_cents": -1000, "currency": "EUR"}
    # First check: no baseline yet, no alert, baseline gets set to 1000
    assert ns._check_recurring(conn, 1, [pattern]) == []
    assert db_module.get_recurring_baseline(conn, 1, 1) == 1000

    # Second check: amount rose >10% -> alert, baseline updated
    pattern2 = {"id": 1, "merchant": "Netflix", "amount_cents": -1300, "currency": "EUR"}
    alerts = ns._check_recurring(conn, 1, [pattern2])
    assert len(alerts) == 1
    assert alerts[0]["type"] == "recurring_increase"
    assert db_module.get_recurring_baseline(conn, 1, 1) == 1300


def test_recurring_increase_silent_within_threshold():
    conn = _conn()
    pattern = {"id": 1, "merchant": "Netflix", "amount_cents": -1000, "currency": "EUR"}
    ns._check_recurring(conn, 1, [pattern])
    pattern2 = {"id": 1, "merchant": "Netflix", "amount_cents": -1050, "currency": "EUR"}
    assert ns._check_recurring(conn, 1, [pattern2]) == []


def _txn(i, amount_cents, category="groceries"):
    return {
        "id": i,
        "amount_cents": amount_cents,
        "currency": "EUR",
        "category": category,
        "normalized_merchant": "Carrefour",
        "raw_label": "CARREFOUR",
        "is_transfer": False,
        "is_income": False,
        "is_refund": False,
    }


def test_transaction_anomaly_detected():
    txns = [_txn(i, -2500) for i in range(5)] + [_txn(99, -30000)]
    alerts = ns._check_transaction_anomalies(txns)
    keys = {a["key"] for a in alerts}
    assert "txn_anomaly:99" in keys
    assert "txn_anomaly:0" not in keys


def test_transaction_anomaly_requires_minimum_samples():
    txns = [_txn(i, -2500) for i in range(3)] + [_txn(99, -30000)]
    assert ns._check_transaction_anomalies(txns) == []


def test_transaction_anomaly_ignores_transfers_income_refunds():
    txns = [_txn(i, -2500) for i in range(5)]
    outlier = _txn(99, -30000)
    outlier["is_transfer"] = True
    alerts = ns._check_transaction_anomalies([*txns, outlier])
    assert alerts == []


def test_pazuru_alerts_are_shaped_into_feed_items():
    items = [
        {"key": "merchant_spike:7", "type": "merchant_spike", "severity": "warning",
         "merchant": "Gym", "amount_cents": 4500, "typical_cents": 1000, "currency": "EUR"},
        {"key": "buffer_breach:1:2026-06-30", "type": "buffer_breach", "severity": "warning",
         "account_name": "Main", "balance_cents": 100000, "buffer_cents": 170000,
         "currency": "EUR"},
        {"key": "fee_spike:2026-06", "type": "fee_spike", "severity": "warning",
         "fees_cents": 2500, "typical_cents": 500, "currency": "EUR"},
        {"key": "x:1", "type": "unknown"},
    ]
    out = ns._pazuru_alerts(items)
    assert [a["type"] for a in out] == ["merchant_spike", "buffer_breach", "fee_spike"]
    assert "45.00 EUR" in out[0]["message"] and "10.00 EUR" in out[0]["message"]
    assert all(set(a) == {"key", "type", "severity", "title", "message"} for a in out)


def test_generate_notifications_merges_pazuru_alerts_and_dedupes(monkeypatch):
    import asyncio

    payloads = {
        "/api/accounts": [],
        "/api/goals": [],
        "/api/recurring": [],
        "/api/transactions": {"items": [_txn(i, -2500) for i in range(5)] + [_txn(99, -30000)]},
        "/api/alerts": {"items": [
            {"key": "merchant_spike:99", "type": "merchant_spike", "severity": "warning",
             "merchant": "M", "amount_cents": 30000, "typical_cents": 2500, "currency": "EUR"},
            {"key": "fee_spike:2026-06", "type": "fee_spike", "severity": "warning",
             "fees_cents": 2500, "typical_cents": 500, "currency": "EUR"},
        ]},
    }

    async def fake_get(client, url, params, cookies):
        return payloads[url[url.index("/api/"):]]

    import settings_store

    monkeypatch.setattr(ns, "_get_json", fake_get)
    conn = _conn()
    settings_store.init_settings(conn)
    keys = {a["key"] for a in asyncio.run(ns.generate_notifications(conn, 1))["items"]}
    assert "txn_anomaly:99" in keys
    assert "merchant_spike:99" not in keys  # already covered by the category outlier
    assert "fee_spike:2026-06" in keys

    db_module.dismiss_notification(conn, 1, "fee_spike:2026-06")
    after = {a["key"] for a in asyncio.run(ns.generate_notifications(conn, 1))["items"]}
    assert "fee_spike:2026-06" not in after
