"""Per-app/per-feature provider preferences and request-time resolution."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import consent
import db
import features
from auth import Caller, require_caller
from config import get_settings

BYOK_PROVIDERS = frozenset(
    {"cloudflare", "openai", "anthropic", "mistral", "gemini", "openrouter"}
)

router = APIRouter(prefix="/v1/prefs", tags=["prefs"])


@dataclass(frozen=True)
class Pref:
    app: str
    feature: str
    provider: str
    byok_provider: str | None


@dataclass(frozen=True)
class Resolution:
    mode: Literal["local", "cloud", "byok"]
    byok_provider: str | None
    notice: str | None


LOCAL = Resolution("local", None, None)


def get_all(conn, user_id: int) -> list[Pref]:
    rows = conn.execute(
        "SELECT app, feature, provider, byok_provider FROM ai_prefs WHERE user_id=? "
        "ORDER BY app, feature",
        (user_id,),
    ).fetchall()
    return [
        Pref(r["app"], r["feature"], r["provider"], r["byok_provider"]) for r in rows
    ]


def put(
    conn, user_id: int, app: str, feature: str, provider: str, byok_provider: str | None
) -> Pref:
    features.validate(app, feature)
    if provider == "byok" and byok_provider not in BYOK_PROVIDERS:
        raise ValueError("byok preference needs a known byok_provider")
    if provider != "byok":
        byok_provider = None
    conn.execute(
        "INSERT INTO ai_prefs(user_id, app, feature, provider, byok_provider, updated_at) "
        "VALUES (?,?,?,?,?,?) ON CONFLICT(user_id, app, feature) DO UPDATE SET "
        "provider=excluded.provider, byok_provider=excluded.byok_provider, "
        "updated_at=excluded.updated_at",
        (user_id, app, feature, provider, byok_provider, datetime.now(UTC).isoformat()),
    )
    conn.commit()
    return Pref(app, feature, provider, byok_provider)


def _pref_for(conn, user_id: int, app: str, feature: str) -> Pref | None:
    for f in (feature, "*"):
        row = conn.execute(
            "SELECT app, feature, provider, byok_provider FROM ai_prefs "
            "WHERE user_id=? AND app=? AND feature=?",
            (user_id, app, f),
        ).fetchone()
        if row:
            return Pref(
                row["app"], row["feature"], row["provider"], row["byok_provider"]
            )
    return None


def resolve(conn, caller: Caller, app: str, feature: str) -> Resolution:
    """feature row -> app default -> local. Consent is read from the DB on every call."""
    pref = _pref_for(conn, caller.user_id, app, feature)
    if pref is None or pref.provider == "local":
        return LOCAL
    s = get_settings()
    if not s.ai_cloud_enabled and caller.user_id not in s.test_allowlist:
        return Resolution("local", None, "cloud_unavailable")
    if pref.provider == "cloud":
        if not consent.is_granted(conn, caller.user_id, "cloudflare"):
            return Resolution("local", None, "consent_required")
        return Resolution("cloud", None, None)
    consent_key = f"byok:{pref.byok_provider}"
    if not consent.is_granted(conn, caller.user_id, consent_key):
        return Resolution("local", None, "consent_required")
    key = conn.execute(
        "SELECT status FROM byok_keys WHERE user_id=? AND provider=?",
        (caller.user_id, pref.byok_provider),
    ).fetchone()
    if key is None or key["status"] != "ok":
        return Resolution("local", None, "byok_key_invalid")
    return Resolution("byok", pref.byok_provider, None)


class PrefIn(BaseModel):
    app: str
    feature: str
    provider: Literal["local", "cloud", "byok"]
    byok_provider: str | None = None


def _out(p: Pref) -> dict:
    return {
        "app": p.app,
        "feature": p.feature,
        "provider": p.provider,
        "byok_provider": p.byok_provider,
    }


@router.get("")
def list_prefs(caller: Caller = Depends(require_caller), conn=Depends(db.get_conn)):  # noqa: B008
    return [_out(p) for p in get_all(conn, caller.user_id)]


@router.put("")
def put_pref(
    body: PrefIn, caller: Caller = Depends(require_caller), conn=Depends(db.get_conn)
):  # noqa: B008
    try:
        pref = put(
            conn,
            caller.user_id,
            body.app,
            body.feature,
            body.provider,
            body.byok_provider,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    return _out(pref)
