"""Public read API — personal API keys (foroba#165, TI-D item 5, Plan A).

Thin wrappers around existing internal services (networth_service, notification_service) —
zero new business logic. Every route requires require_api_key (401 unauthenticated, 403
audience-gated, 402 tier-gated) plus a per-key rate limit stricter than the browser-facing
default (RATE_LIMIT_DEFAULT).
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request

import networth_service
import notification_service
from auth import keys
from auth.api_key_auth import api_key_rate_limit_key, require_api_key
from auth.conn import get_conn
from auth.security import create_token
from config import settings
from rate_limit import limiter
from stepup import issue_stepup_cookies

router = APIRouter(prefix="/api/public/v1", tags=["public-api"])


def _cookie_for(user: dict) -> str:
    """Public-API requests carry no suite_session cookie — mint a short-lived one so the
    wrapped internal services can still fan out to Pazuru/Tsumi on the user's behalf."""
    private_key, _, kid = keys.get_keypair(settings)
    return create_token(
        user["id"],
        private_key,
        settings.jwt_ttl_minutes,
        tier=user["tier"],
        audience=user["audience"],
        is_admin=bool(user["is_admin"]),
        kid=kid,
    )


@router.get("/networth")
@limiter.limit("30/minute", key_func=api_key_rate_limit_key)
async def public_networth(
    request: Request,
    days: int = 365,
    user: dict = Depends(require_api_key),
) -> dict:
    # foroba#215: no interactive browser session to forward stepup_<app> cookies
    # from -- mint them directly (see stepup.issue_stepup_cookies docstring).
    stepup = issue_stepup_cookies(user["id"])
    return await networth_service.fetch_networth(
        days,
        cookie=_cookie_for(user),
        stepup_pazuru=stepup["pazuru"],
        stepup_tsumi=stepup["tsumi"],
    )


@router.get("/notifications")
@limiter.limit("30/minute", key_func=api_key_rate_limit_key)
async def public_notifications(
    request: Request,
    user: dict = Depends(require_api_key),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    stepup = issue_stepup_cookies(user["id"])
    return await notification_service.generate_notifications(
        conn, user["id"], cookie=_cookie_for(user), stepup_pazuru=stepup["pazuru"]
    )
