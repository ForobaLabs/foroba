"""Resolve the current user from the suite_session cookie."""
from __future__ import annotations

import sqlite3

import jwt
from fastapi import Cookie, Depends, HTTPException, status

from config import settings
from auth import repository as repo
from auth.conn import get_conn
from auth.security import decode_token


def get_current_user(
    conn: sqlite3.Connection = Depends(get_conn),
    suite_session: str | None = Cookie(default=None),
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


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
