"""Resolve the current user from the suite_session cookie."""
from __future__ import annotations

import os
import sqlite3

import jwt
from fastapi import Cookie, Depends, HTTPException, status

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


def get_current_user(
    conn: sqlite3.Connection = Depends(get_conn),
    suite_session: str | None = Cookie(default=None),
) -> dict:
    if os.getenv("AUTH_DEV_BYPASS", "false").lower() == "true":
        return _DEV_USER
    if not suite_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        _, public_key, _ = keys.get_keypair(settings)
        claims = decode_token(suite_session, public_key)
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
