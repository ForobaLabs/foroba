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
        {"id": 1, "name": "Emergency fund", "saved_cents": 100000, "currency": "EUR", "is_achieved": True},
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
    alerts = ns._check_transaction_anomalies(txns + [outlier])
    assert alerts == []
