"""Idempotent subscription state machine; the only billing writer of users.tier."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from billing.events import SubscriptionEvent

PREMIUM_STATUSES = {"active", "trialing"}


def tier_for(status: str, since: datetime, now: datetime, grace_days: int) -> str:
    """premium while paid/trialing; past_due keeps premium for `grace_days` after it began."""
    if status in PREMIUM_STATUSES:
        return "premium"
    if status == "past_due":
        return "premium" if now - since <= timedelta(days=grace_days) else "free"
    return "free"


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


def recompute_tier(
    conn: sqlite3.Connection, user_id: int, *, now: datetime, grace_days: int
) -> str:
    """Premium if ANY of the user's subscriptions currently grants it. Caller commits."""
    rows = conn.execute(
        "SELECT status, last_event_at FROM subscriptions WHERE user_id = ?", (user_id,)
    ).fetchall()
    tier = "free"
    for row in rows:
        since = datetime.fromisoformat(row["last_event_at"])
        if tier_for(row["status"], since, now, grace_days) == "premium":
            tier = "premium"
            break
    conn.execute("UPDATE users SET tier = ? WHERE id = ?", (tier, user_id))
    return tier


def apply_event(
    conn: sqlite3.Connection,
    ev: SubscriptionEvent,
    *,
    now: datetime | None = None,
    grace_days: int = 7,
) -> str:
    """Return applied | duplicate | stale | ignored. Never stores the raw payload."""
    now = now or datetime.now(UTC)
    cur = conn.execute(
        "INSERT OR IGNORE INTO billing_events (event_id, event_type, occurred_at) VALUES (?, ?, ?)",
        (ev.event_id, ev.event_type, _iso(ev.occurred_at)),
    )
    if cur.rowcount == 0:
        conn.commit()
        return "duplicate"
    user = (
        conn.execute("SELECT id, is_admin FROM users WHERE id = ?", (ev.user_id,)).fetchone()
        if ev.user_id
        else None
    )
    if user is None:
        conn.commit()
        return "ignored"
    existing = conn.execute(
        "SELECT last_event_at FROM subscriptions "
        "WHERE provider = 'paddle' AND provider_subscription_id = ?",
        (ev.subscription_id,),
    ).fetchone()
    if existing and existing["last_event_at"] > _iso(ev.occurred_at):
        conn.commit()
        return "stale"
    conn.execute(
        "INSERT INTO subscriptions (user_id, provider, provider_subscription_id, "
        "provider_customer_id, status, "
        "current_period_end, cancel_at_period_end, last_event_at, updated_at) "
        "VALUES (?, 'paddle', ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(provider, provider_subscription_id) DO UPDATE SET "
        "status=excluded.status, current_period_end=excluded.current_period_end, "
        "cancel_at_period_end=excluded.cancel_at_period_end, last_event_at=excluded.last_event_at, "
        "provider_customer_id=COALESCE(excluded.provider_customer_id, provider_customer_id), "
        "updated_at=excluded.updated_at",
        (
            ev.user_id,
            ev.subscription_id,
            ev.customer_id,
            ev.status,
            _iso(ev.period_end),
            1 if ev.cancel_at_period_end else 0,
            _iso(ev.occurred_at),
            _iso(now),
        ),
    )
    if not user["is_admin"]:
        recompute_tier(conn, ev.user_id, now=now, grace_days=grace_days)
    conn.commit()
    return "applied"
