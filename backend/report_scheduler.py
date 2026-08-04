"""APScheduler — monthly AI report generation (foroba#159, TI-D item 2).

Runs on the 1st of every month at 03:00 local time. For every user with
`banking.monthly_ai_report` unlocked, generates that month's report with up to
3 retries (5s/15s/30s backoff) within the same run — 4 attempts total. Never
skips a user silently — every eligible user without an existing row this month
ends the run with a 'success' or 'failed' row; failures are logged (auto-captured
by GlitchTip, TI-B item 2, sentry_sdk already wired in observability.py).

Design note: if a row already exists for (user, year_month) — e.g. the user
already manually generated a report this month before the 1st — the scheduled
run skips (logged info, not an error) rather than consuming another quota slot;
manual "Generate"/"Retry" via the API remain the quota-scoped paths for
additional reports within the same month.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import db
import monthly_report_service as mrs
from auth import keys
from auth.conn import get_conn
from auth.entitlements import evaluate
from auth.repository import list_all_users
from auth.security import create_token
from config import settings
from settings_store import get_all
from stepup import issue_stepup_cookies

logger = logging.getLogger("foroba.report_scheduler")

_RETRY_DELAYS_SECONDS = [5, 15, 30]


async def _generate_for_user(conn, user: dict, year_month: str, token: str) -> None:
    existing = db.count_monthly_reports_this_month(conn, user_id=user["id"], year_month=year_month)
    if existing > 0:
        logger.info(
            "Monthly report already exists for user %s (%s) — skipping scheduled run",
            user["id"],
            year_month,
        )
        return

    row = db.create_monthly_report(
        conn, user_id=user["id"], year_month=year_month, trigger="scheduled"
    )
    # foroba#215: no interactive browser session to forward stepup_<app> cookies
    # from -- mint them directly (see stepup.issue_stepup_cookies docstring).
    stepup = issue_stepup_cookies(user["id"])
    for delay in [0, *_RETRY_DELAYS_SECONDS]:
        if delay:
            await asyncio.sleep(delay)
        row = await mrs._run_generation(
            conn,
            row,
            user,
            cookie=token,
            stepup_pazuru=stepup["pazuru"],
            stepup_tsumi=stepup["tsumi"],
        )
        if row["status"] == "success":
            return
    logger.error(
        "Monthly report generation exhausted %d attempts for user %s (%s): %s",
        len(_RETRY_DELAYS_SECONDS) + 1,
        user["id"],
        year_month,
        row["error_message"],
    )


async def _generate_all_monthly_reports_async() -> None:
    conn = get_conn()
    year_month = date.today().strftime("%Y-%m")
    runtime = get_all(conn)
    gating_enabled = runtime.get("premium_gating_enabled", "false") == "true"
    private_key, _, kid = keys.get_keypair(settings)

    users = list_all_users(conn)
    eligible = [
        u
        for u in users
        if evaluate("banking.monthly_ai_report", u, gating_enabled=gating_enabled).unlocked
    ]
    logger.info("Monthly report scheduler: %d eligible user(s) for %s", len(eligible), year_month)

    for user in eligible:
        token = create_token(
            user["id"],
            private_key,
            settings.jwt_ttl_minutes,
            tier=user["tier"],
            audience=user["audience"],
            is_admin=bool(user["is_admin"]),
            kid=kid,
        )
        try:
            await _generate_for_user(conn, user, year_month, token)
        except Exception:
            logger.exception("Unexpected error generating monthly report for user %s", user["id"])


def generate_all_monthly_reports() -> None:
    """Sync entry point for APScheduler (thread-based, not asyncio-native)."""
    asyncio.run(_generate_all_monthly_reports_async())


def start_report_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        generate_all_monthly_reports,
        trigger=CronTrigger(day=1, hour=3, minute=0),
        id="monthly_ai_report",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("Monthly AI report scheduler started (runs 1st of month at 03:00).")
    return scheduler
