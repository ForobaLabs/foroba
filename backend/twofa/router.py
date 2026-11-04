"""2FA enrollment, verification, and disable endpoints — TOTP, Email OTP, WebAuthn (passkey
enable/disable flag only; the WebAuthn ceremony itself lives in passkeys/router.py), plus
methods listing/removal and recovery-code regeneration."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

import security_log
from auth import repository as repo
from auth.conn import get_conn
from auth.dependencies import get_current_user
from auth.models import EmailOtpVerifyRequest, MfaMethodsResponse, RecoveryCodesResponse
from auth.security import verify_password
from email_otp import EmailNotConfiguredError, generate_and_send
from email_otp import verify_and_consume as verify_email_otp
from passkeys.service import has_current_credential
from rate_limit import limiter
from recovery_codes import generate_and_store, remaining_count
from twofa.totp import generate_secret, provisioning_uri, qr_data_url, verify_code

router = APIRouter(prefix="/auth/2fa", tags=["2fa"])


class CodeRequest(BaseModel):
    code: str


@router.post("/enroll")
@limiter.limit("20/minute")
async def enroll(
    request: Request,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    fresh = repo.get_user_by_id(conn, user["id"])
    if fresh and fresh["totp_enabled"]:
        # FOR-D06: re-enrolling on an already-MFA-enrolled account must re-confirm the
        # current password (same pattern as PUT /auth/me/password) before staging a new
        # secret — otherwise a stale/replayed /enroll call could be used to prepare a
        # takeover, and set_totp_secret() must never disable a working MFA method on its own.
        try:
            body = await request.json()
        except json.JSONDecodeError:
            body = {}
        current_password = (body or {}).get("current_password")
        if not current_password or not verify_password(current_password, fresh["password_hash"]):
            raise HTTPException(401, "Current password required to re-enroll")
    secret = generate_secret()
    repo.set_totp_secret(conn, user["id"], secret)
    uri = provisioning_uri(secret, account=user["email"])
    return {"secret": secret, "qr": qr_data_url(uri)}


@router.post("/verify")
@limiter.limit("10/minute")
def verify(
    request: Request,
    req: CodeRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    fresh = repo.get_user_by_id(conn, user["id"])
    pending_secret = fresh["totp_secret_pending"] or fresh["totp_secret"]
    if not pending_secret or not verify_code(pending_secret, req.code):
        security_log.log_event(conn, user_id=user["id"], event="mfa_failed",
                               detail="invalid TOTP code",
                               ip=request.client.host if request.client else None)
        raise HTTPException(400, "Invalid code")
    repo.enable_totp(conn, user["id"])
    _ensure_recovery_codes(conn, user["id"])
    return {"enabled": True}


@router.post("/disable")
@limiter.limit("20/minute")
def disable(
    request: Request,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    _block_if_last_method(conn, user["id"], "totp")
    repo.disable_totp(conn, user["id"])
    return {"enabled": False}


@router.post("/email-otp/send")
@limiter.limit("5/minute")
def email_otp_send(
    request: Request,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    try:
        generate_and_send(conn, user["id"], user["email"])
    except EmailNotConfiguredError as exc:
        raise HTTPException(503, "Email delivery is not configured") from exc
    return {"sent": True}


@router.post("/email-otp/verify")
@limiter.limit("10/minute")
def email_otp_verify(
    request: Request,
    req: EmailOtpVerifyRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    if not verify_email_otp(conn, user["id"], req.code):
        raise HTTPException(400, "Invalid or expired code")
    repo.enable_email_otp(conn, user["id"])
    _ensure_recovery_codes(conn, user["id"])
    return {"enabled": True}


@router.get("/methods", response_model=MfaMethodsResponse)
def methods(
    user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    fresh = repo.get_user_by_id(conn, user["id"])
    if fresh is None:
        # AUTH_DEV_BYPASS's synthetic user has no row in `users` — report the
        # only sensible state for a user with no persisted account: nothing enrolled.
        return {
            "totp_enabled": False,
            "email_otp_enabled": False,
            "webauthn_enabled": False,
            "recovery_codes_remaining": 0,
        }
    return {
        "totp_enabled": bool(fresh["totp_enabled"]),
        "email_otp_enabled": bool(fresh["email_otp_enabled"]),
        # A passkey bound to a previous RP ID can never verify: don't offer it.
        "webauthn_enabled": bool(fresh["webauthn_enabled"])
        and has_current_credential(conn, user["id"]),
        "recovery_codes_remaining": remaining_count(conn, user["id"]),
    }


@router.delete("/methods/{method}")
def remove_method(
    method: str,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    if method not in {"totp", "email_otp", "webauthn"}:
        raise HTTPException(404, "Unknown method")
    _block_if_last_method(conn, user["id"], method)
    if method == "totp":
        repo.disable_totp(conn, user["id"])
    elif method == "email_otp":
        repo.disable_email_otp(conn, user["id"])
    else:
        repo.disable_webauthn(conn, user["id"])
    return {"removed": method}


@router.post("/recovery-codes/regenerate", response_model=RecoveryCodesResponse)
@limiter.limit("5/minute")
def recovery_codes_regenerate(
    request: Request,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    return {"codes": generate_and_store(conn, user["id"])}


def _block_if_last_method(conn: sqlite3.Connection, user_id: int, removing: str) -> None:
    """A user must always keep at least one enrolled second-factor method. Recovery codes are a
    one-time-use fallback for losing access to an enrolled method, not a substitute for having
    zero methods enrolled — so they don't count towards this minimum."""
    fresh = repo.get_user_by_id(conn, user_id)
    enabled = {
        "totp": bool(fresh["totp_enabled"]),
        "email_otp": bool(fresh["email_otp_enabled"]),
        "webauthn": bool(fresh["webauthn_enabled"]),
    }
    enabled[removing] = False
    if not any(enabled.values()):
        raise HTTPException(400, "Cannot remove your last remaining MFA method")


def _ensure_recovery_codes(conn: sqlite3.Connection, user_id: int) -> None:
    """Generate the initial recovery-code set the first time any method is enrolled."""
    if remaining_count(conn, user_id) == 0:
        generate_and_store(conn, user_id)
