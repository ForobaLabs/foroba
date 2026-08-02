"""WebAuthn (passkey) registration + authentication endpoints."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import repository as repo
from auth.conn import get_conn
from auth.dependencies import get_current_user
from auth.models import WebauthnRegisterRequest
from passkeys.service import (
    authentication_options_for_user,
    registration_options_for_user,
    verify_registration,
)
from rate_limit import limiter

router = APIRouter(prefix="/auth/webauthn", tags=["webauthn"])


@router.post("/register/options")
@limiter.limit("20/minute")
def register_options(
    request: Request,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    return json.loads(registration_options_for_user(conn, user["id"], user["email"]))


@router.post("/authenticate/options")
@limiter.limit("20/minute")
def authenticate_options(
    request: Request,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    return json.loads(authentication_options_for_user(conn, user["id"]))


@router.post("/register/verify")
@limiter.limit("20/minute")
def register_verify(
    request: Request,
    req: WebauthnRegisterRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    try:
        verify_registration(conn, user["id"], req.credential, label=req.label)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    repo.enable_webauthn(conn, user["id"])
    return {"enabled": True}
