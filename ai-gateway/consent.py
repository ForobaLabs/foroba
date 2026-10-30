"""Versioned, withdrawable consent per external provider. Append-only event log."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

import db
from auth import Caller, require_caller

CONSENT_VERSION = "2026-10-30"
PROVIDERS = frozenset(
    {
        "cloudflare",
        "byok:openai",
        "byok:anthropic",
        "byok:mistral",
        "byok:gemini",
        "byok:openrouter",
        "byok:cloudflare",
    }
)

router = APIRouter(prefix="/v1/consents", tags=["consent"])


def _now() -> str:
    return datetime.now(UTC).isoformat()


def record(conn, user_id: int, provider: str, action: str, ip: str | None) -> None:
    conn.execute(
        "INSERT INTO ai_consents(user_id, provider, action, version, at, ip) VALUES (?,?,?,?,?,?)",
        (user_id, provider, action, CONSENT_VERSION, _now(), ip),
    )
    conn.commit()


def _latest(conn, user_id: int, provider: str):
    return conn.execute(
        "SELECT action, version, at FROM ai_consents WHERE user_id=? AND provider=? "
        "ORDER BY id DESC LIMIT 1",
        (user_id, provider),
    ).fetchone()


def is_granted(conn, user_id: int, provider: str) -> bool:
    row = _latest(conn, user_id, provider)
    return bool(row and row["action"] == "accept" and row["version"] == CONSENT_VERSION)


class ConsentIn(BaseModel):
    provider: str


def _check(provider: str) -> None:
    if provider not in PROVIDERS:
        raise HTTPException(status_code=422, detail="unknown provider")


@router.get("")
def list_consents(caller: Caller = Depends(require_caller), conn=Depends(db.get_conn)):  # noqa: B008
    out = []
    for p in sorted(PROVIDERS):
        row = _latest(conn, caller.user_id, p)
        out.append(
            {
                "provider": p,
                "granted": is_granted(conn, caller.user_id, p),
                "version": row["version"] if row else None,
                "at": row["at"] if row else None,
            }
        )
    return out


@router.post("", status_code=204)
def accept(
    body: ConsentIn, caller: Caller = Depends(require_caller), conn=Depends(db.get_conn)
):  # noqa: B008
    _check(body.provider)
    record(conn, caller.user_id, body.provider, "accept", caller.ip)
    return Response(status_code=204)


@router.delete("/{provider:path}", status_code=204)
def withdraw(
    provider: str, caller: Caller = Depends(require_caller), conn=Depends(db.get_conn)
):  # noqa: B008
    _check(provider)
    record(conn, caller.user_id, provider, "withdraw", caller.ip)
    return Response(status_code=204)
