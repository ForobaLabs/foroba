"""Tests for webhook_dispatch_job: HMAC signing, dedup, retry/auto-disable (foroba#165,
TI-D item 5, Plan A)."""
from __future__ import annotations

import hashlib
import hmac
import sqlite3

import httpx
import pytest

import db
import webhook_dispatch_job as wdj


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_schema(c)
    return c


def test_sign_matches_hmac_sha256():
    body = b'{"event": "goal_reached"}'
    signature = wdj._sign("my-secret", body)
    expected = "sha256=" + hmac.new(b"my-secret", body, hashlib.sha256).hexdigest()
    assert signature == expected


@pytest.mark.asyncio
async def test_deliver_event_skips_if_already_delivered_successfully(conn):
    webhook = dict(db.create_webhook(conn, user_id=1, target_url="https://x.test/hook", signing_secret="sec"))
    db.upsert_webhook_delivery_success(conn, webhook["id"], "goal_reached:1", 1)

    calls = []

    class _FakeClient:
        async def post(self, *a, **k):
            calls.append(1)
            raise AssertionError("should not POST — already delivered")

    await wdj._deliver_event(
        _FakeClient(), conn, webhook, {"event_key": "goal_reached:1", "event": "goal_reached", "data": {}}
    )
    assert calls == []


@pytest.mark.asyncio
async def test_deliver_event_success_resets_failure_count(conn):
    webhook = dict(db.create_webhook(conn, user_id=1, target_url="https://x.test/hook", signing_secret="sec"))
    db.register_webhook_failure(conn, webhook["id"])

    class _FakeResponse:
        def raise_for_status(self):
            pass

    class _FakeClient:
        async def post(self, *a, **k):
            return _FakeResponse()

    await wdj._deliver_event(
        _FakeClient(), conn, webhook, {"event_key": "goal_reached:1", "event": "goal_reached", "data": {}}
    )

    delivery = db.get_webhook_delivery(conn, webhook["id"], "goal_reached:1")
    assert delivery["last_status"] == "success"
    updated_webhook = db.get_webhook(conn, webhook["id"], user_id=1)
    assert updated_webhook["consecutive_failures"] == 0


@pytest.mark.asyncio
async def test_deliver_event_retries_before_marking_failed(conn):
    webhook = dict(db.create_webhook(conn, user_id=1, target_url="https://x.test/hook", signing_secret="sec"))

    class _FailingClient:
        async def post(self, *a, **k):
            raise httpx.ConnectError("boom")

    event = {"event_key": "goal_reached:1", "event": "goal_reached", "data": {}}

    await wdj._deliver_event(_FailingClient(), conn, webhook, event)
    delivery = db.get_webhook_delivery(conn, webhook["id"], "goal_reached:1")
    assert delivery["attempt_count"] == 1
    assert delivery["last_status"] == "pending"
    assert db.get_webhook(conn, webhook["id"], user_id=1)["consecutive_failures"] == 0

    await wdj._deliver_event(_FailingClient(), conn, webhook, event)
    await wdj._deliver_event(_FailingClient(), conn, webhook, event)
    delivery = db.get_webhook_delivery(conn, webhook["id"], "goal_reached:1")
    assert delivery["attempt_count"] == 3
    assert delivery["last_status"] == "failed"
    assert db.get_webhook(conn, webhook["id"], user_id=1)["consecutive_failures"] == 1


@pytest.mark.asyncio
async def test_deliver_event_auto_disables_webhook_after_ten_failed_events(conn):
    webhook = dict(db.create_webhook(conn, user_id=1, target_url="https://x.test/hook", signing_secret="sec"))

    class _FailingClient:
        async def post(self, *a, **k):
            raise httpx.ConnectError("boom")

    for event_num in range(10):
        event = {"event_key": f"goal_reached:{event_num}", "event": "goal_reached", "data": {}}
        for _ in range(3):
            await wdj._deliver_event(_FailingClient(), conn, webhook, event)

    updated = db.get_webhook(conn, webhook["id"], user_id=1)
    assert updated["consecutive_failures"] == 10
    assert updated["is_active"] == 0
    assert updated["disabled_at"] is not None
