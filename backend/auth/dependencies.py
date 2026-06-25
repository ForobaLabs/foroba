"""Resolve the current user from the suite_session cookie."""
from __future__ import annotations

import sqlite3

import jwt
from fastapi import Cookie, HTTPException, status

from config import settings
from auth import repository as repo
from auth.security import decode_token


def get_current_user(
    conn: sqlite3.Connection,
    suite_session: str | None = None,
) -> dict:
    if not suite_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        claims = decode_token(suite_session, settings.suite_jwt_secret)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
    user = repo.get_user_by_id(conn, int(claims["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return user
