"""Cookieless token endpoints for native clients (iOS).

The web app authenticates with the `suite_session` httpOnly cookie set by
`auth/router.py`. A native app cannot rely on cookies across a WKWebView / URLSession
boundary, so it uses this parallel surface instead: the same credential checks, but the
access token is returned in the JSON body and paired with an opaque rotating refresh
token stored in the Keychain.

These handlers deliberately never call `_set_session_cookie`.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from auth import keys, refresh_tokens
from auth import repository as repo
from auth.conn import get_conn
from auth.dependencies import get_current_user
from auth.models import UserPublic
from auth.security import create_token, hash_password, needs_rehash, verify_password
from config import settings
from email_otp import verify_and_consume as verify_email_otp
from rate_limit import limiter
from twofa.totp import verify_code

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenRequest(BaseModel):
    email: EmailStr
    password: str
    device_label: str = Field(min_length=1, max_length=64)


class Token2FARequest(BaseModel):
    email: EmailStr
    code: str
    method: str
    device_label: str = Field(min_length=1, max_length=64)


class RefreshRequest(BaseModel):
    refresh_token: str


def _issue_pair(conn: sqlite3.Connection, user: dict, device_label: str) -> dict:
    private_key, _, kid = keys.get_keypair(settings)
    access = create_token(
        user["id"],
        private_key,
        settings.access_token_ttl_minutes,
        tier=user.get("tier", "free"),
        audience=user.get("audience", "base"),
        is_admin=bool(user.get("is_admin", 0)),
        kid=kid,
        session_version=user.get("session_version", 1),
    )
    refresh = refresh_tokens.issue(conn, user["id"], device_label)
    return {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": settings.access_token_ttl_minutes * 60,
        "refresh_token": refresh,
        "user": UserPublic(**user).model_dump(),
    }


def _guard_account(user: dict | None) -> None:
    if user is not None and repo.is_locked_out(user):
        raise HTTPException(
            status.HTTP_423_LOCKED,
            "Account temporarily locked. Try again later.",
        )
    if user is not None and user.get("account_disabled"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been disabled.")


@router.post("/token", response_model=None)
@limiter.limit("10/minute")
def token(
    request: Request,
    req: TokenRequest,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    # Local import to avoid circular import between the two routers.
    from auth.router import _enabled_methods, _has_any_mfa_method

    user = repo.get_user_by_email(conn, req.email)
    _guard_account(user)
    if user is None or not verify_password(req.password, user["password_hash"]):
        if user is not None:
            repo.register_failed_login(conn, user["id"])
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if needs_rehash(user["password_hash"]):
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(req.password), user["id"]),
        )
        conn.commit()
    if _has_any_mfa_method(user) and settings.auth_2fa_enabled:
        return {
            "mfa_required": True,
            "email": user["email"],
            "methods": _enabled_methods(user),
        }
    repo.reset_failed_login(conn, user["id"])
    return _issue_pair(conn, user, req.device_label)


@router.post("/token/2fa", response_model=None)
@limiter.limit("10/minute")
def token_2fa(
    request: Request,
    req: Token2FARequest,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    user = repo.get_user_by_email(conn, req.email)
    _guard_account(user)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "2FA not set up")
    if req.method == "totp":
        ok = (
            bool(user.get("totp_enabled"))
            and bool(user.get("totp_secret"))
            and verify_code(user["totp_secret"], req.code)
        )
    elif req.method == "email_otp":
        ok = bool(user.get("email_otp_enabled")) and verify_email_otp(conn, user["id"], req.code)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported method")
    if not ok:
        repo.register_failed_login(conn, user["id"])
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid code")
    repo.reset_failed_login(conn, user["id"])
    return _issue_pair(conn, user, req.device_label)


@router.post("/token/refresh", response_model=None)
@limiter.limit("30/minute")
def refresh(
    request: Request,
    req: RefreshRequest,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    try:
        new_refresh, session = refresh_tokens.rotate(conn, req.refresh_token)
    except refresh_tokens.ReuseDetected:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Refresh token reuse detected"
        ) from None
    except refresh_tokens.InvalidRefreshToken:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid refresh token"
        ) from None
    user = repo.get_user_by_id(conn, session["user_id"])
    if user is None or user.get("account_disabled"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    private_key, _, kid = keys.get_keypair(settings)
    access = create_token(
        user["id"],
        private_key,
        settings.access_token_ttl_minutes,
        tier=user.get("tier", "free"),
        audience=user.get("audience", "base"),
        is_admin=bool(user.get("is_admin", 0)),
        kid=kid,
        session_version=user.get("session_version", 1),
    )
    return {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": settings.access_token_ttl_minutes * 60,
        "refresh_token": new_refresh,
        "user": UserPublic(**user).model_dump(),
    }


@router.post("/token/revoke", status_code=204)
def revoke(req: RefreshRequest, conn: sqlite3.Connection = Depends(get_conn)) -> None:
    # Returns 204 even for an unknown token — exposing 404 would be an oracle
    # for guessing valid refresh tokens.
    refresh_tokens.revoke(conn, req.refresh_token)


@router.get("/sessions")
def list_sessions(
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    return {"sessions": refresh_tokens.list_sessions(conn, user["id"])}


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: int,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    if not refresh_tokens.revoke_session(conn, user["id"], session_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
