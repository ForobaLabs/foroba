"""2FA enrollment, verification, and disable endpoints.
These endpoints exist regardless of the AUTH_2FA_ENABLED flag.
The flag only controls login enforcement (see auth/router)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import repository as repo
from auth.conn import get_conn
from auth.dependencies import get_current_user
from rate_limit import limiter
from twofa.totp import generate_secret, provisioning_uri, qr_data_url, verify_code

router = APIRouter(prefix="/auth/2fa", tags=["2fa"])


class CodeRequest(BaseModel):
    code: str


@router.post("/enroll")
@limiter.limit("20/minute")
def enroll(
    request: Request,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
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
    if not fresh["totp_secret"] or not verify_code(fresh["totp_secret"], req.code):
        raise HTTPException(400, "Invalid code")
    repo.enable_totp(conn, user["id"])
    return {"enabled": True}


@router.post("/disable")
@limiter.limit("20/minute")
def disable(
    request: Request,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    repo.disable_totp(conn, user["id"])
    return {"enabled": False}
