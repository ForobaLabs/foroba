"""/billing routes. All inert (503) until settings.billing_enabled is true."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth.conn import get_conn
from auth.dependencies import get_current_user
from billing.events import parse_paddle_event
from billing.paddle_signature import SignatureError, verify_signature
from billing.provider import BillingProviderError, Plan, get_provider
from billing.service import apply_event
from config import settings

router = APIRouter(prefix="/billing", tags=["billing"])


def _require_enabled() -> None:
    if not settings.billing_enabled:
        raise HTTPException(status_code=503, detail="Billing is not enabled")


class CheckoutRequest(BaseModel):
    plan: Plan


@router.post("/webhook")
async def webhook(request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    _require_enabled()
    body = await request.body()
    try:
        verify_signature(
            request.headers.get("Paddle-Signature", ""), body, settings.paddle_webhook_secret
        )
    except SignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature") from None
    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload") from None
    event = parse_paddle_event(payload)
    if event is None:
        return {"result": "ignored"}
    return {"result": apply_event(conn, event, grace_days=settings.billing_grace_days)}


@router.get("/status")
def status(user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_conn)):
    row = conn.execute(
        "SELECT status, current_period_end, cancel_at_period_end FROM subscriptions "
        "WHERE user_id = ? ORDER BY last_event_at DESC LIMIT 1",
        (user["id"],),
    ).fetchone()
    return {
        "enabled": bool(settings.billing_enabled),
        "subscription": None
        if row is None
        else {
            "status": row["status"],
            "current_period_end": row["current_period_end"],
            "cancel_at_period_end": bool(row["cancel_at_period_end"]),
        },
    }


@router.post("/checkout-session")
def checkout_session(body: CheckoutRequest, user: dict = Depends(get_current_user)):
    _require_enabled()
    try:
        url = get_provider(settings.billing_provider).create_checkout(
            user_id=user["id"], email=user["email"], plan=body.plan
        )
    except BillingProviderError:
        raise HTTPException(status_code=501, detail="Checkout is not available") from None
    return {"url": url}
