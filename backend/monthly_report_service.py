"""Monthly AI-generated financial report (foroba#159, TI-D item 2).

Shared core used by both the scheduled job (report_scheduler.py) and the manual
generate/retry endpoints (monthly_report_router.py). Reuses jeli_service's existing
Pazuru/Tsumi context gathering — no new upstream endpoints.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from pathlib import Path

import db
import jeli_service
from auth.conn import get_conn
from config import settings
from email_service import send_email
from jeli_output_guard import sanitize_reply

logger = logging.getLogger(__name__)

MONTHLY_REPORT_LIMIT = 6

PROMPT_TEMPLATE = (Path(__file__).parent / "prompts" / "monthly_report_system.txt").read_text()


class QuotaExceededError(Exception):
    def __init__(self, limit: int):
        self.limit = limit
        super().__init__(f"Monthly report limit reached ({limit})")


class ReportNotFoundError(Exception):
    pass


class InvalidRetryError(Exception):
    """Raised when retry is attempted on a report that isn't in 'failed' status."""


async def _run_generation(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    user: dict,
    *,
    cookie: str | None,
    stepup_pazuru: str | None = None,
    stepup_tsumi: str | None = None,
) -> sqlite3.Row:
    """Run one generation attempt against an existing row, update it in place with
    the result, and return the updated row. Never raises — always leaves the row in
    'success' or 'failed' with a reason (never a silent skip)."""
    attempt_count = row["attempt_count"] + 1
    try:
        pazuru_ctx, tsumi_ctx = await jeli_service.gather_context(
            settings.pazuru_api_url.rstrip("/"),
            settings.tsumi_api_url.rstrip("/"),
            cookie,
            stepup_pazuru=stepup_pazuru,
            stepup_tsumi=stepup_tsumi,
        )
        system_prompt = PROMPT_TEMPLATE.format(
            user_name=user.get("name") or "the user",
            year_month=row["year_month"],
            pazuru_context=pazuru_ctx,
            tsumi_context=tsumi_ctx,
        )
        narrative = await jeli_service.generate_narrative(
            system_prompt, f"Summarize {row['year_month']} for me."
        )
        narrative = sanitize_reply(narrative, context_text=f"{pazuru_ctx}\n{tsumi_ctx}")
        snapshot = json.dumps({"pazuru_context": pazuru_ctx, "tsumi_context": tsumi_ctx})
        updated = db.update_monthly_report_result(
            conn,
            row["id"],
            status="success",
            narrative_text=narrative,
            context_snapshot_json=snapshot,
            error_message=None,
            attempt_count=attempt_count,
        )
        send_email(
            user["email"],
            f"Your {row['year_month']} financial report is ready",
            narrative[:500],
        )
        return updated
    except Exception as exc:
        logger.exception(
            "Monthly report generation failed for user %s (%s)", user["id"], row["year_month"]
        )
        error_text = str(exc) or type(exc).__name__
        return db.update_monthly_report_result(
            conn,
            row["id"],
            status="failed",
            narrative_text=row["narrative_text"],
            context_snapshot_json=row["context_snapshot_json"],
            error_message=error_text[:500],
            attempt_count=attempt_count,
        )


def start_new_report(
    conn: sqlite3.Connection,
    user: dict,
    year_month: str,
    trigger: str,
) -> dict:
    """Quota-check and create the row for a new report. Fast/synchronous — does NOT
    run generation; the caller schedules run_generation_in_background separately so
    the ~300s LLM call never blocks the HTTP response. Raises QuotaExceededError if
    the (user, year_month) cap is already reached."""
    count = db.count_monthly_reports_this_month(conn, user_id=user["id"], year_month=year_month)
    if count >= MONTHLY_REPORT_LIMIT:
        raise QuotaExceededError(MONTHLY_REPORT_LIMIT)
    return db.create_monthly_report(
        conn, user_id=user["id"], year_month=year_month, trigger=trigger
    )


def start_retry(conn: sqlite3.Connection, user: dict, report_id: int) -> dict:
    """Validate a failed report and flip it back to 'generating'. Fast/synchronous —
    does NOT run generation; the caller schedules run_generation_in_background
    separately. Never consumes quota."""
    row = db.get_monthly_report(conn, report_id, user_id=user["id"])
    if row is None:
        raise ReportNotFoundError(report_id)
    if row["status"] != "failed":
        raise InvalidRetryError(row["status"])
    return db.update_monthly_report_result(
        conn,
        report_id,
        status="generating",
        narrative_text=row["narrative_text"],
        context_snapshot_json=row["context_snapshot_json"],
        error_message=None,
        attempt_count=row["attempt_count"],
    )


def run_generation_in_background(
    report_id: int,
    user: dict,
    *,
    cookie: str | None,
    stepup_pazuru: str | None = None,
    stepup_tsumi: str | None = None,
) -> None:
    """Sync entry point for FastAPI's BackgroundTasks, which runs it on its own
    worker thread (not the request's) — mirrors report_scheduler.py's
    sync-wrapper-over-asyncio.run pattern for the same reason: fetch a fresh
    thread-local conn via get_conn() here rather than reusing the request's
    connection object, since that object is tied to whichever thread served the
    request and reusing it from a different thread would reintroduce the
    cross-thread shared-connection race fixed in foroba#170 (see auth/conn.py)."""
    asyncio.run(
        _run_generation_in_background_async(
            report_id, user, cookie=cookie, stepup_pazuru=stepup_pazuru, stepup_tsumi=stepup_tsumi
        )
    )


async def _run_generation_in_background_async(
    report_id: int,
    user: dict,
    *,
    cookie: str | None,
    stepup_pazuru: str | None,
    stepup_tsumi: str | None,
) -> None:
    conn = get_conn()
    row = db.get_monthly_report(conn, report_id, user_id=user["id"])
    if row is None:
        logger.error(
            "Background generation could not find report %s for user %s", report_id, user["id"]
        )
        return
    await _run_generation(
        conn, row, user, cookie=cookie, stepup_pazuru=stepup_pazuru, stepup_tsumi=stepup_tsumi
    )
