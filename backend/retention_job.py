"""CL-2.3 — per-category retention enforcement (GDPR art.5(e), foroba#240).

Each rule = (table, timestamp_column, ttl_days). TTLs are set conservatively here;
the CL-1 data-retention-policy.md remains the source of truth. Legal-hold rows
(open dsar_requests) are excluded from deletion until resolved.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# (table, timestamp_col, ttl_days)
_RULES = [
    ("webauthn_challenges", "created_at", 1),   # challenge tokens: expire after 1 day
    ("dsar_requests", "resolved_at", 365),        # fulfilled DSARs: keep 1 year then purge
]


def purge_expired(conn, now_days: int | None = None) -> dict[str, int]:
    """Delete rows older than ttl_days. Returns {table: rows_deleted}.

    Args:
        conn: sqlite3 connection (in tests: in-memory; in prod: from get_conn())
        now_days: override TTL for all rules (used in tests to control 'now')
    """
    deleted: dict[str, int] = {}
    for table, col, ttl in _RULES:
        ttl_to_use = ttl if now_days is None else now_days
        where = f"{col} < datetime('now', ?)"
        params: list = [f"-{ttl_to_use} days"]
        if table == "dsar_requests":
            where += " AND status = 'fulfilled'"
        cur = conn.execute(f"DELETE FROM {table} WHERE {where}", params)
        deleted[table] = cur.rowcount
    conn.commit()
    logger.info("retention purge: %s", deleted)
    return deleted


def start_retention_scheduler() -> None:
    """Wire the retention job into APScheduler (runs daily at 03:30)."""
    from apscheduler.schedulers.background import BackgroundScheduler

    from db import get_conn

    sched = BackgroundScheduler()

    def _run() -> None:
        with get_conn() as conn:
            purge_expired(conn)

    sched.add_job(_run, "cron", hour=3, minute=30)
    sched.start()
    logger.info("retention scheduler started")
