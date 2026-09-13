"""Resolve the current user from Bearer header (native) or suite_session cookie (web)."""

from __future__ import annotations

import os
import sqlite3

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, status

from auth import keys
from auth import repository as repo
from auth.conn import get_conn
from auth.security import decode_token
from config import settings

_DEV_USER: dict = {
    "id": 0,
    "email": "dev@localhost.dev",
    "name": "Dev User",
    "tier": "free",
    "audience": "base",
    "audience_locked": False,
    "is_admin": False,
    "totp_enabled": False,
    "household_id": None,
    "display_currency": "EUR",
    "show_debts": False,
}


def _token_from_header(authorization: str | None) -> str | None:
    """Extract credential from `Authorization: Bearer <token>`.

    Returns None for any other scheme so the caller falls back to the cookie.
    """
    if not authorization:
        return None
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    credential = credential.strip()
    return credential or None


def get_current_user(
    conn: sqlite3.Connection = Depends(get_conn),
    suite_session: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    token = _token_from_header(authorization) or suite_session
    if not token:
        if os.getenv("AUTH_DEV_BYPASS", "false").lower() == "true":
            return _DEV_USER
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        _, public_key, _ = keys.get_keypair(settings)
        claims = decode_token(token, public_key)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session") from None
    user = repo.get_user_by_id(conn, int(claims["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
