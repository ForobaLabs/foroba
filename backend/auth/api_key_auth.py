"""API-key auth dependency for the public read API (foroba#165, TI-D item 5, Plan A)."""
from __future__ import annotations

import sqlite3

from fastapi import Depends, Header, HTTPException, Request, status

import db
from auth.conn import get_conn
from auth.entitlements import evaluate
from auth.repository import get_user_by_id
from auth.security import verify_password
from settings_store import get_all

FEATURE_KEY = "platform.public_api"


def require_api_key(
    authorization: str | None = Header(default=None),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or malformed Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    key_prefix, sep, secret = token.rpartition(".")
    if not sep:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed API key")

    row = db.get_api_key_by_prefix(conn, key_prefix)
    if row is None or not row["is_active"] or not verify_password(secret, row["secret_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    user = get_user_by_id(conn, row["user_id"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")

    runtime = get_all(conn)
    gating_enabled = runtime.get("premium_gating_enabled", "false") == "true"
    access = evaluate(FEATURE_KEY, user, gating_enabled=gating_enabled)
    if not access.visible:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, {"error": {"code": "audience_required", "feature": FEATURE_KEY}}
        )
    if not access.unlocked:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED, {"error": {"code": "premium_required", "feature": FEATURE_KEY}}
        )

    db.touch_api_key_last_used(conn, row["id"])
    return user


def api_key_rate_limit_key(request: Request) -> str:
    """slowapi key_func: rate-limit per API key prefix, not per IP — a single leaked
    key's budget never affects other users' requests."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
        prefix, sep, _ = token.rpartition(".")
        if sep:
            return prefix
    return "anonymous"
