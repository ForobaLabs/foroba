"""Internal read of the persisted session-version floors (AI-6-F4).

Foroba bumps `users.session_version` on logout and pushes the new floor to Pazuru and
Tsumi, which hold it in memory. A restart there would forget every revocation, so
those apps re-pull this list from the database of record on first use after boot.
Only users above the default floor of 1 are returned.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from auth.conn import get_conn
from handoff_router import _require_internal_token

router = APIRouter(
    prefix="/internal/session-floors",
    tags=["internal"],
    dependencies=[Depends(_require_internal_token)],
)


@router.get("")
def list_session_floors(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    rows = conn.execute(
        "SELECT id, session_version FROM users WHERE session_version > 1"
    ).fetchall()
    return {"floors": {str(r["id"]): r["session_version"] for r in rows}}
