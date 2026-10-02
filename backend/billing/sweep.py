"""Daily sweep: past_due only changes on the next webhook, so expire its grace here."""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime, timedelta

from billing.service import recompute_tier

logger = logging.getLogger(__name__)


def sweep_expired(
    conn: sqlite3.Connection, *, now: datetime | None = None, grace_days: int = 7
) -> int:
    """Downgrade users whose only premium source is a past_due subscription beyond grace.

    Returns the number of users downgraded. Admins are never touched.
    """
    now = now or datetime.now(UTC)
    cutoff = (now - timedelta(days=grace_days)).isoformat()
    candidates = conn.execute(
        "SELECT DISTINCT s.user_id FROM subscriptions s JOIN users u ON u.id = s.user_id "
        "WHERE s.status = 'past_due' AND s.last_event_at < ? "
        "AND u.tier = 'premium' AND u.is_admin = 0",
        (cutoff,),
    ).fetchall()
    changed = 0
    for row in candidates:
        if recompute_tier(conn, row["user_id"], now=now, grace_days=grace_days) == "free":
            changed += 1
    conn.commit()
    if changed:
        logger.info("billing sweep: %d user(s) downgraded after past_due grace", changed)
    return changed


def start_billing_sweep_scheduler() -> None:
    """Daily 04:10; a no-op unless billing is enabled."""
    from apscheduler.schedulers.background import BackgroundScheduler

    from auth.conn import get_conn
    from config import settings

    if not settings.billing_enabled:
        return
    sched = BackgroundScheduler()

    def _run() -> None:
        sweep_expired(get_conn(), grace_days=settings.billing_grace_days)

    sched.add_job(_run, "cron", hour=4, minute=10)
    sched.start()
