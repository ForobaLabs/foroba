"""Notification/alert generation — deterministic checks over Pazuru data (foroba#158).

Fan-out to Pazuru (accounts, goals, recurring, transactions), mirroring
networth_service.py's resilient style: a failed upstream section is simply
skipped (never raises, never blocks the other checks). Four alert types,
all deterministic (no LLM call — consistent with the suite's trust-critical
analytics philosophy):

  - balance_low: an account balance below a configurable threshold
    (settings_store "low_balance_threshold_cents"), re-fires once per day
    per account.
  - goal_reached: a Pazuru savings goal Pazuru itself marked as achieved.
  - recurring_increase: a recurring payment's amount rose >10% since the
    last check. Pazuru's RecurringPattern only stores current state (no
    history), so the previous amount is tracked as a baseline in Foroba's
    own DB (recurring_amount_baselines) and updated on every check.
  - txn_anomaly: a transaction whose absolute amount is >3x the median for
    its category within the fetched window — a simple, deterministic
    outlier check, not a statistical model.

Every alert carries a stable `key` (see individual `_check_*` functions)
so a user's dismissal (notification_dismissals table, checked by the
caller) permanently suppresses that specific alert instance.
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import date
from statistics import median
from typing import Any

import httpx

import db
import settings_store
from config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 4.0
ANOMALY_MULTIPLIER = 3.0
ANOMALY_MIN_CATEGORY_SAMPLES = 5
RECURRING_INCREASE_THRESHOLD = 1.10


async def _get_json(
    client: httpx.AsyncClient, url: str, params: dict[str, Any], cookie: str | None
) -> Any | None:
    cookies = {"suite_session": cookie} if cookie else None
    try:
        resp = await client.get(url, params=params, cookies=cookies, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("notification source unavailable (%s): %s", url, exc)
        return None


def _check_balance_low(accounts: list[dict[str, Any]], threshold_cents: int) -> list[dict[str, Any]]:
    today = date.today().isoformat()
    alerts = []
    for acc in accounts:
        if acc["balance_cents"] < threshold_cents:
            alerts.append(
                {
                    "key": f"balance_low:{acc['id']}:{today}",
                    "type": "balance_low",
                    "severity": "warning",
                    "title": "Low balance",
                    "message": (
                        f"{acc['display_name']} balance is "
                        f"{acc['balance_cents'] / 100:.2f} {acc['currency']}, "
                        f"below your {threshold_cents / 100:.2f} threshold."
                    ),
                }
            )
    return alerts


def _check_goals(goals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "key": f"goal_reached:{g['id']}",
            "type": "goal_reached",
            "severity": "positive",
            "title": "Goal reached",
            "message": (
                f"You reached your goal \"{g['name']}\" "
                f"({g['saved_cents'] / 100:.2f} {g['currency']})."
            ),
        }
        for g in goals
        if g.get("is_achieved")
    ]


def _check_recurring(
    conn: sqlite3.Connection, user_id: int, patterns: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    alerts = []
    for p in patterns:
        pattern_id = p["id"]
        amount = abs(p["amount_cents"])
        baseline = db.get_recurring_baseline(conn, user_id, pattern_id)
        if baseline is not None and amount > baseline * RECURRING_INCREASE_THRESHOLD:
            alerts.append(
                {
                    "key": f"recurring_increase:{pattern_id}:{amount}",
                    "type": "recurring_increase",
                    "severity": "warning",
                    "title": "Recurring payment increased",
                    "message": (
                        f"{p['merchant']} rose from {baseline / 100:.2f} to "
                        f"{amount / 100:.2f} {p['currency']}."
                    ),
                }
            )
        if baseline is None or amount != baseline:
            db.set_recurring_baseline(conn, user_id, pattern_id, amount)
    return alerts


def _check_transaction_anomalies(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relevant = [
        t
        for t in transactions
        if not t["is_transfer"] and not t["is_income"] and not t["is_refund"] and t["category"]
    ]
    by_category: dict[str, list[int]] = {}
    for t in relevant:
        by_category.setdefault(t["category"], []).append(abs(t["amount_cents"]))

    alerts = []
    for t in relevant:
        amounts = by_category[t["category"]]
        if len(amounts) < ANOMALY_MIN_CATEGORY_SAMPLES:
            continue
        m = median(amounts)
        if m > 0 and abs(t["amount_cents"]) > m * ANOMALY_MULTIPLIER:
            alerts.append(
                {
                    "key": f"txn_anomaly:{t['id']}",
                    "type": "txn_anomaly",
                    "severity": "warning",
                    "title": "Unusual transaction",
                    "message": (
                        f"{t['normalized_merchant'] or t['raw_label']} — "
                        f"{abs(t['amount_cents']) / 100:.2f} {t['currency']} is much higher "
                        f"than usual for {t['category']}."
                    ),
                }
            )
    return alerts


async def generate_notifications(
    conn: sqlite3.Connection, user_id: int, *, cookie: str | None = None
) -> dict[str, Any]:
    """Compute active (non-dismissed) alerts for one user. Never raises."""
    pazuru_base = settings.pazuru_api_url.rstrip("/")
    threshold_cents = int(
        settings_store.get_all(conn).get("low_balance_threshold_cents", "10000")
    )

    async with httpx.AsyncClient() as client:
        accounts, goals, recurring, transactions = await asyncio.gather(
            _get_json(client, f"{pazuru_base}/api/accounts", {}, cookie),
            _get_json(client, f"{pazuru_base}/api/goals", {}, cookie),
            _get_json(client, f"{pazuru_base}/api/recurring", {}, cookie),
            _get_json(
                client, f"{pazuru_base}/api/transactions", {"page_size": 200}, cookie
            ),
        )

    degraded = any(x is None for x in (accounts, goals, recurring, transactions))

    alerts: list[dict[str, Any]] = []
    if accounts is not None:
        alerts += _check_balance_low(accounts, threshold_cents)
    if goals is not None:
        alerts += _check_goals(goals)
    if recurring is not None:
        alerts += _check_recurring(conn, user_id, recurring)
    if transactions is not None:
        alerts += _check_transaction_anomalies(transactions.get("items", []))

    dismissed = db.get_dismissed_notification_keys(conn, user_id)
    active = [a for a in alerts if a["key"] not in dismissed]

    return {"items": active, "degraded": degraded}
