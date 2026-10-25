"""GET /fx/rates — latest EUR-based FX rates, for the frontend currency
dropdown + client-side conversion (TI-D item 3 Plan 3, foroba#164)."""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, Request

import fx_service
from auth.conn import get_conn
from rate_limit import limiter

router = APIRouter(prefix="/fx", tags=["fx"])


def _get_latest_rates(conn: sqlite3.Connection) -> dict[str, float]:
    """Return {currency: rate_to_eur} for the most recent cached date of each currency."""
    rows = conn.execute(
        """
        SELECT currency, rate_to_eur FROM fx_rates f
        WHERE rate_date = (
            SELECT MAX(rate_date) FROM fx_rates WHERE currency = f.currency
        )
        ORDER BY currency
        """
    ).fetchall()
    return {r["currency"]: r["rate_to_eur"] for r in rows}


@router.get("/rates")
@limiter.limit("60/minute")  # Plan AU L-4: unauthenticated and refreshes from upstream
def get_fx_rates(request: Request, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """Return cached FX rates, refreshing today's rates first if not yet cached."""
    fx_service.refresh_latest_rates(conn)
    return {
        "base": "EUR",
        "date": date.today().isoformat(),
        "rates": _get_latest_rates(conn),
    }
