"""Monthly AI-generated financial report (foroba#159, TI-D item 2).

Shared core used by both the scheduled job (report_scheduler.py) and the manual
generate/retry endpoints (monthly_report_router.py). Reuses jeli_service's existing
Pazuru/Tsumi context gathering — no new upstream endpoints.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

import db
import jeli_service
from config import settings
from email_service import send_email

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
        return db.update_monthly_report_result(
            conn,
            row["id"],
            status="failed",
            narrative_text=row["narrative_text"],
            context_snapshot_json=row["context_snapshot_json"],
            error_message=str(exc)[:500],
            attempt_count=attempt_count,
        )


async def generate_new_report(
    conn: sqlite3.Connection,
    user: dict,
    year_month: str,
    trigger: str,
    *,
    cookie: str | None,
) -> sqlite3.Row:
    """Create a new report row and run generation once. Consumes quota — raises
    QuotaExceededError if the (user, year_month) cap is already reached."""
    count = db.count_monthly_reports_this_month(conn, user_id=user["id"], year_month=year_month)
    if count >= MONTHLY_REPORT_LIMIT:
        raise QuotaExceededError(MONTHLY_REPORT_LIMIT)
    row = db.create_monthly_report(conn, user_id=user["id"], year_month=year_month, trigger=trigger)
    return await _run_generation(conn, row, user, cookie=cookie)


async def retry_report(
    conn: sqlite3.Connection,
    user: dict,
    report_id: int,
    *,
    cookie: str | None,
) -> sqlite3.Row:
    """Retry a failed report in place — never consumes quota."""
    row = db.get_monthly_report(conn, report_id, user_id=user["id"])
    if row is None:
        raise ReportNotFoundError(report_id)
    if row["status"] != "failed":
        raise InvalidRetryError(row["status"])
    return await _run_generation(conn, row, user, cookie=cookie)
