"""GDPR hooks called by Foroba's account export/deletion (token-only, no user JWT)."""

from fastapi import APIRouter, Depends, Response

import db
from auth import require_internal

router = APIRouter(
    prefix="/v1/users", tags=["gdpr"], dependencies=[Depends(require_internal)]
)

TABLES = ("ai_consents", "ai_prefs", "byok_keys", "ai_usage")


@router.get("/{user_id}/export")
def export(user_id: int, conn=Depends(db.get_conn)):  # noqa: B008
    q = lambda sql: [dict(r) for r in conn.execute(sql, (user_id,))]  # noqa: E731
    return {
        "consents": q(
            "SELECT provider, action, version, at, ip FROM ai_consents WHERE user_id=? ORDER BY id"
        ),
        "prefs": q(
            "SELECT app, feature, provider, byok_provider, updated_at FROM ai_prefs "
            "WHERE user_id=? ORDER BY app, feature"
        ),
        "byok": q(
            "SELECT provider, model, status, created_at FROM byok_keys WHERE user_id=? ORDER BY provider"
        ),
        "usage_months": q(
            "SELECT substr(at,1,7) AS month, COALESCE(SUM(neurons),0) AS neurons, COUNT(*) AS requests "
            "FROM ai_usage WHERE user_id=? GROUP BY month ORDER BY month"
        ),
    }


@router.delete("/{user_id}", status_code=204)
def erase(user_id: int, conn=Depends(db.get_conn)):  # noqa: B008
    for table in TABLES:
        conn.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))  # noqa: S608
    conn.commit()
    return Response(status_code=204)
