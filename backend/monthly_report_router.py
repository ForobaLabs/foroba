"""Monthly AI report routes (foroba#159, TI-D item 2)."""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Cookie, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import db
import monthly_report_service as mrs
import pdf_service
from auth.conn import get_conn
from auth.entitlements_router import require_feature

router = APIRouter(prefix="/reports/monthly", tags=["monthly-reports"])

FEATURE_KEY = "banking.monthly_ai_report"


class ReportOut(BaseModel):
    id: int
    year_month: str
    trigger: str
    status: str
    narrative_text: str | None
    error_message: str | None
    attempt_count: int
    created_at: str
    updated_at: str


def _to_out(row: sqlite3.Row) -> ReportOut:
    return ReportOut(
        id=row["id"],
        year_month=row["year_month"],
        trigger=row["trigger"],
        status=row["status"],
        narrative_text=row["narrative_text"],
        error_message=row["error_message"],
        attempt_count=row["attempt_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("/")
def list_reports(
    year_month: str | None = None,
    user: dict = Depends(require_feature(FEATURE_KEY)),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    rows = db.list_monthly_reports(conn, user_id=user["id"], year_month=year_month)
    current_month = year_month or date.today().strftime("%Y-%m")
    used = db.count_monthly_reports_this_month(conn, user_id=user["id"], year_month=current_month)
    return {
        "items": [_to_out(r).model_dump() for r in rows],
        "quota": {"used": used, "limit": mrs.MONTHLY_REPORT_LIMIT},
    }


class GenerateIn(BaseModel):
    year_month: str


@router.post("/generate")
async def generate(
    body: GenerateIn,
    user: dict = Depends(require_feature(FEATURE_KEY)),
    conn: sqlite3.Connection = Depends(get_conn),
    suite_session: str | None = Cookie(default=None),
    stepup_pazuru: str | None = Cookie(default=None),
    stepup_tsumi: str | None = Cookie(default=None),
) -> ReportOut:
    try:
        row = await mrs.generate_new_report(
            conn,
            user,
            body.year_month,
            trigger="manual",
            cookie=suite_session,
            stepup_pazuru=stepup_pazuru,
            stepup_tsumi=stepup_tsumi,
        )
    except mrs.QuotaExceededError as exc:
        raise HTTPException(429, {"error": "monthly_limit_reached", "limit": exc.limit}) from exc
    return _to_out(row)


@router.get("/{report_id}")
def get_report(
    report_id: int,
    user: dict = Depends(require_feature(FEATURE_KEY)),
    conn: sqlite3.Connection = Depends(get_conn),
) -> ReportOut:
    row = db.get_monthly_report(conn, report_id, user_id=user["id"])
    if row is None:
        raise HTTPException(404, "Report not found")
    return _to_out(row)


@router.post("/{report_id}/retry")
async def retry(
    report_id: int,
    user: dict = Depends(require_feature(FEATURE_KEY)),
    conn: sqlite3.Connection = Depends(get_conn),
    suite_session: str | None = Cookie(default=None),
    stepup_pazuru: str | None = Cookie(default=None),
    stepup_tsumi: str | None = Cookie(default=None),
) -> ReportOut:
    try:
        row = await mrs.retry_report(
            conn,
            user,
            report_id,
            cookie=suite_session,
            stepup_pazuru=stepup_pazuru,
            stepup_tsumi=stepup_tsumi,
        )
    except mrs.ReportNotFoundError as exc:
        raise HTTPException(404, "Report not found") from exc
    except mrs.InvalidRetryError as exc:
        raise HTTPException(409, {"error": "not_failed", "status": str(exc)}) from exc
    return _to_out(row)


@router.get("/{report_id}/pdf")
def get_pdf(
    report_id: int,
    user: dict = Depends(require_feature(FEATURE_KEY)),
    conn: sqlite3.Connection = Depends(get_conn),
) -> StreamingResponse:
    row = db.get_monthly_report(conn, report_id, user_id=user["id"])
    if row is None:
        raise HTTPException(404, "Report not found")
    if row["status"] != "success":
        raise HTTPException(409, {"error": "not_ready", "status": row["status"]})
    pdf_bytes = pdf_service.render_pdf(
        year_month=row["year_month"], narrative_text=row["narrative_text"] or ""
    )
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report-{row["year_month"]}.pdf"'},
    )
