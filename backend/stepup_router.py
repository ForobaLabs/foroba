"""Cross-app step-up challenge + refresh endpoints (MFA hardening, foroba#199)."""

from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from auth import repository as repo
from auth.conn import get_conn
from auth.dependencies import get_current_user
from config import settings
from email_otp import verify_and_consume as verify_email_otp
from passkeys.service import verify_authentication as verify_webauthn_authentication
from rate_limit import limiter
from recovery_codes import verify_and_consume as verify_recovery_code
from stepup import StepupTokenError, issue_stepup_token, verify_stepup_token
from twofa.totp import verify_code as verify_totp_code

router = APIRouter(prefix="/auth/stepup", tags=["stepup"])

_VALID_APPS = {"pazuru", "tsumi"}


class StepupVerifyRequest(BaseModel):
    app: Literal["pazuru", "tsumi"]
    method: Literal["totp", "email_otp", "recovery_code", "webauthn"]
    code: str | None = None
    credential: str | None = None


@router.post("/verify")
@limiter.limit("10/minute")
def stepup_verify(
    request: Request,
    req: StepupVerifyRequest,
    response: Response,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    fresh = repo.get_user_by_id(conn, user["id"])
    ok = False
    if req.method == "totp" and fresh.get("totp_enabled") and req.code:
        ok = verify_totp_code(fresh["totp_secret"], req.code)
    elif req.method == "email_otp" and fresh.get("email_otp_enabled") and req.code:
        ok = verify_email_otp(conn, user["id"], req.code)
    elif req.method == "recovery_code" and req.code:
        ok = verify_recovery_code(conn, user["id"], req.code)
    elif req.method == "webauthn" and fresh.get("webauthn_enabled") and req.credential:
        ok = verify_webauthn_authentication(conn, user["id"], req.credential)
    if not ok:
        raise HTTPException(401, "Step-up verification failed")
    token = issue_stepup_token(user_id=user["id"], app=req.app)
    response.set_cookie(
        f"stepup_{req.app}",
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.stepup_ttl_minutes * 60,
        domain=settings.cookie_domain or None,
    )
    return {"verified": True}


class StepupRefreshRequest(BaseModel):
    app: Literal["pazuru", "tsumi"]
    token: str


@router.post("/refresh")
@limiter.limit("120/minute")
def stepup_refresh(
    request: Request,
    req: StepupRefreshRequest,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """Server-to-server call from Pazuru/Tsumi's backend (not the browser — the old token is
    passed in the body, not read from a cookie, since Pazuru/Tsumi hold it locally). Re-verifies
    the account is still valid (not disabled) before minting a fresh token, so a disabled account
    can't keep sliding its step-up window forward."""
    try:
        claims = verify_stepup_token(req.token, expected_app=req.app)
    except StepupTokenError as exc:
        raise HTTPException(401, str(exc)) from exc
    user = repo.get_user_by_id(conn, int(claims["sub"]))
    if user is None or user.get("account_disabled"):
        raise HTTPException(401, "Account no longer valid")
    return {"token": issue_stepup_token(user_id=user["id"], app=req.app)}
