"""Cross-app step-up challenge + refresh endpoints (MFA hardening, foroba#199)."""

from __future__ import annotations

import hmac
import sqlite3
import time
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
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
    x_client: str | None = Header(default=None),
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
    token = issue_stepup_token(
        user_id=user["id"], app=req.app, session_version=int(fresh.get("session_version") or 1)
    )
    response.set_cookie(
        f"stepup_{req.app}",
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.stepup_ttl_minutes * 60,
        domain=settings.cookie_domain or None,
    )
    if (x_client or "").lower() == "native":
        return {"app": req.app, "token": token}
    return {"verified": True}


class StepupRefreshRequest(BaseModel):
    app: Literal["pazuru", "tsumi"]
    token: str


def _require_internal_token(x_internal_token: str = Header(default="")) -> None:
    """Refresh is server-to-server only (Pazuru/Tsumi backends); browsers never hold
    the shared secret. Unconfigured secret = endpoint closed (Plan AU M-1)."""
    expected = settings.internal_api_token
    if not expected or not hmac.compare_digest(x_internal_token, expected):
        raise HTTPException(403, "Forbidden")


@router.post("/refresh", dependencies=[Depends(_require_internal_token)])
@limiter.limit("120/minute")
def stepup_refresh(
    request: Request,
    req: StepupRefreshRequest,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """Server-to-server call from Pazuru/Tsumi's backend (not the browser — the old token is
    passed in the body, not read from a cookie, since Pazuru/Tsumi hold it locally). Re-verifies
    the account is still valid (not disabled, session floor not raised) and that the original
    MFA proof is younger than `stepup_max_age_hours` before minting a fresh token."""
    try:
        claims = verify_stepup_token(req.token, expected_app=req.app)
    except StepupTokenError as exc:
        raise HTTPException(401, str(exc)) from exc
    auth_time = int(claims.get("auth_time", claims["iat"]))
    if time.time() - auth_time > settings.stepup_max_age_hours * 3600:
        raise HTTPException(401, "Step-up expired; verify again")
    user = repo.get_user_by_id(conn, int(claims["sub"]))
    if user is None or user.get("account_disabled"):
        raise HTTPException(401, "Account no longer valid")
    session_version = int(user.get("session_version") or 1)
    if int(claims.get("sv", 1)) < session_version:
        raise HTTPException(401, "Session revoked")
    return {
        "token": issue_stepup_token(
            user_id=user["id"], app=req.app, auth_time=auth_time, session_version=session_version
        )
    }
