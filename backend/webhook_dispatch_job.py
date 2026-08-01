"""Webhook delivery job — scheduled poll of alerts, HMAC-signed push delivery (foroba#165,
TI-D item 5, Plan A).

Runs every 15 minutes via APScheduler (registered in main.py alongside
report_scheduler.py). For every user with at least one active webhook: computes the
current alert list via notification_service.generate_notifications() (the same source
the pull-based /notifications route uses) plus any monthly report that has status
"success". Each alert/event carries a stable event_key (mirrors notification_service's
alert "key" field, e.g. "goal_reached:42", or f"monthly_report:{report_id}"). Delivery is
deduped via the webhook_deliveries unique constraint — an event never fires twice
successfully to the same webhook. Bounded retry (3 attempts) before an event is marked
permanently "failed"; a webhook auto-disables after 10 consecutive failed events,
protecting the scheduler from wasting cycles on a dead endpoint.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

import db
import notification_service
from auth import keys
from auth.conn import get_conn
from auth.repository import get_user_by_id
from auth.security import create_token
from config import settings

logger = logging.getLogger("foroba.webhook_dispatch_job")

_TIMEOUT = 5.0
_MAX_ATTEMPTS = 3
_AUTO_DISABLE_THRESHOLD = 10


def _sign(signing_secret: str, body: bytes) -> str:
    digest = hmac.new(signing_secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


async def _events_for_user(conn, user: dict, cookie: str) -> list[dict]:
    """Alerts (from notification_service) + monthly reports with status='success'."""
    notifications = await notification_service.generate_notifications(
        conn, user["id"], cookie=cookie
    )
    events = [
        {"event_key": a["key"], "event": a["type"], "data": a} for a in notifications["items"]
    ]
    for report in db.list_monthly_reports(conn, user_id=user["id"]):
        if report["status"] == "success":
            events.append(
                {
                    "event_key": f"monthly_report:{report['id']}",
                    "event": "monthly_report_ready",
                    "data": {"id": report["id"], "year_month": report["year_month"]},
                }
            )
    return events


async def _deliver_event(client, conn, webhook: dict, event: dict) -> None:
    existing = db.get_webhook_delivery(conn, webhook["id"], event["event_key"])
    if existing is not None and existing["last_status"] == "success":
        return  # dedup — already delivered

    attempt_count = (existing["attempt_count"] if existing else 0) + 1
    body = json.dumps(
        {
            "event": event["event"],
            "data": event["data"],
            "timestamp": datetime.now(UTC).isoformat(),
        }
    ).encode()

    try:
        resp = await client.post(
            webhook["target_url"],
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Foroba-Signature": _sign(webhook["signing_secret"], body),
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        db.upsert_webhook_delivery_success(conn, webhook["id"], event["event_key"], attempt_count)
        db.reset_webhook_failures(conn, webhook["id"])
        return
    except Exception as exc:
        logger.warning(
            "webhook delivery failed (webhook=%s, event=%s): %s",
            webhook["id"],
            event["event_key"],
            exc,
        )

    if attempt_count < _MAX_ATTEMPTS:
        db.upsert_webhook_delivery_attempt(
            conn, webhook["id"], event["event_key"], attempt_count=attempt_count, status="pending"
        )
        return

    db.upsert_webhook_delivery_attempt(
        conn, webhook["id"], event["event_key"], attempt_count=attempt_count, status="failed"
    )
    updated = db.register_webhook_failure(conn, webhook["id"])
    if not updated["is_active"]:
        logger.warning(
            "webhook %s auto-disabled after %d consecutive failures",
            webhook["id"],
            updated["consecutive_failures"],
        )


async def _dispatch_all_async() -> None:
    conn = get_conn()
    active_webhooks = db.list_active_webhooks(conn)
    if not active_webhooks:
        return

    by_user: dict[int, list[dict]] = {}
    for w in active_webhooks:
        by_user.setdefault(w["user_id"], []).append(dict(w))

    private_key, _, kid = keys.get_keypair(settings)

    async with httpx.AsyncClient() as client:
        for user_id, webhooks in by_user.items():
            user = get_user_by_id(conn, user_id)
            if user is None:
                continue
            token = create_token(
                user["id"],
                private_key,
                settings.jwt_ttl_minutes,
                tier=user["tier"],
                audience=user["audience"],
                is_admin=bool(user["is_admin"]),
                kid=kid,
            )
            try:
                events = await _events_for_user(conn, user, token)
            except Exception:
                logger.exception("failed to compute events for user %s", user_id)
                continue
            for webhook in webhooks:
                for event in events:
                    try:
                        await _deliver_event(client, conn, webhook, event)
                    except Exception:
                        logger.exception(
                            "unexpected error delivering webhook %s event %s",
                            webhook["id"],
                            event["event_key"],
                        )


def dispatch_all_webhooks() -> None:
    """Sync entry point for APScheduler (thread-based, not asyncio-native)."""
    asyncio.run(_dispatch_all_async())


def start_webhook_dispatch_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        dispatch_all_webhooks,
        trigger=IntervalTrigger(minutes=15),
        id="webhook_dispatch",
        replace_existing=True,
        misfire_grace_time=300,
    )
    scheduler.start()
    logger.info("Webhook dispatch scheduler started (runs every 15 minutes).")
    return scheduler
