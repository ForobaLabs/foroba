"""Billing foundation (BR-12): signature, event parsing, idempotent tier sync, routes."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import db
from auth import repository as repo
from auth.conn import get_conn
from auth.dependencies import get_current_user
from billing.events import parse_paddle_event
from billing.paddle_signature import SignatureError, verify_signature
from billing.service import apply_event, tier_for
from billing.sweep import sweep_expired
from config import settings
from main import app

SECRET = "pdl_ntfset_test_secret"
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


def sign(body: bytes, ts: int, secret: str = SECRET) -> str:
    h1 = hmac.new(secret.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}"


def payload(
    event_id="evt_1",
    etype="subscription.activated",
    status="active",
    user_id="1",
    sub="sub_1",
    occurred="2026-11-01T10:00:00Z",
    ends="2026-12-01T10:00:00Z",
    cancel=False,
):
    return {
        "event_id": event_id,
        "event_type": etype,
        "occurred_at": occurred,
        "data": {
            "id": sub,
            "status": status,
            "customer_id": "ctm_1",
            "custom_data": {"user_id": user_id},
            "current_billing_period": {"ends_at": ends},
            "scheduled_change": {"action": "cancel", "effective_at": ends} if cancel else None,
        },
    }


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    repo.create_user(
        c, email="b@test.local", name="B", password_hash="x", tier="free", audience="base"
    )
    return c


# --- signature -------------------------------------------------------------
def test_signature_accepts_valid():
    body = b'{"a":1}'
    ts = int(NOW.timestamp())
    verify_signature(sign(body, ts), body, SECRET, now=NOW)


@pytest.mark.parametrize("header", ["", "garbage", "ts=abc;h1=00", "h1=00", "ts=1"])
def test_signature_rejects_malformed(header):
    with pytest.raises(SignatureError):
        verify_signature(header, b"{}", SECRET, now=NOW)


def test_signature_rejects_tampered_body():
    ts = int(NOW.timestamp())
    with pytest.raises(SignatureError):
        verify_signature(sign(b'{"a":1}', ts), b'{"a":2}', SECRET, now=NOW)


def test_signature_rejects_wrong_secret_and_empty_secret():
    body, ts = b"{}", int(NOW.timestamp())
    with pytest.raises(SignatureError):
        verify_signature(sign(body, ts, "other"), body, SECRET, now=NOW)
    with pytest.raises(SignatureError):
        verify_signature(sign(body, ts, ""), body, "", now=NOW)


def test_signature_rejects_replay_outside_tolerance():
    body = b"{}"
    ts = int((NOW - timedelta(minutes=10)).timestamp())
    with pytest.raises(SignatureError):
        verify_signature(sign(body, ts), body, SECRET, now=NOW)


def test_signature_accepts_rotated_second_h1():
    body, ts = b"{}", int(NOW.timestamp())
    good = sign(body, ts).split("h1=")[1]
    verify_signature(f"ts={ts};h1={'0' * 64};h1={good}", body, SECRET, now=NOW)


# --- parsing -----------------------------------------------------------------
def test_parse_subscription_event():
    ev = parse_paddle_event(payload(cancel=True))
    assert (ev.event_id, ev.subscription_id, ev.user_id, ev.status) == (
        "evt_1",
        "sub_1",
        1,
        "active",
    )
    assert ev.cancel_at_period_end is True
    assert ev.period_end == datetime(2026, 12, 1, 10, 0, tzinfo=UTC)


def test_parse_ignores_non_subscription_and_bad_input():
    assert (
        parse_paddle_event({"event_id": "e", "event_type": "transaction.completed", "data": {}})
        is None
    )
    assert parse_paddle_event({}) is None
    assert parse_paddle_event(payload(user_id="abc")).user_id is None
    assert parse_paddle_event(payload(status="weird")).status == "weird"


# --- tier derivation -----------------------------------------------------------
@pytest.mark.parametrize(
    "status,expected",
    [
        ("active", "premium"),
        ("trialing", "premium"),
        ("past_due", "premium"),
        ("paused", "free"),
        ("canceled", "free"),
        ("weird", "free"),
    ],
)
def test_tier_for_status(status, expected):
    assert tier_for(status, NOW, NOW + timedelta(days=1), grace_days=7) == expected


def test_past_due_loses_premium_after_grace():
    assert tier_for("past_due", NOW - timedelta(days=8), NOW, grace_days=7) == "free"


# --- apply_event -----------------------------------------------------------------
def user(conn):
    return repo.get_user_by_email(conn, "b@test.local")


def test_activation_grants_premium_and_is_idempotent(conn):
    ev = parse_paddle_event(payload())
    assert apply_event(conn, ev, now=NOW) == "applied"
    assert user(conn)["tier"] == "premium"
    assert apply_event(conn, ev, now=NOW) == "duplicate"
    assert conn.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0] == 1


def test_cancellation_downgrades(conn):
    apply_event(conn, parse_paddle_event(payload()), now=NOW)
    ev = parse_paddle_event(
        payload(
            event_id="evt_2",
            etype="subscription.canceled",
            status="canceled",
            occurred="2026-11-02T10:00:00Z",
        )
    )
    assert apply_event(conn, ev, now=NOW) == "applied"
    assert user(conn)["tier"] == "free"


def test_out_of_order_older_event_is_ignored(conn):
    apply_event(
        conn,
        parse_paddle_event(
            payload(
                event_id="evt_2",
                status="canceled",
                etype="subscription.canceled",
                occurred="2026-11-02T10:00:00Z",
            )
        ),
        now=NOW,
    )
    late = parse_paddle_event(payload(event_id="evt_1", occurred="2026-11-01T10:00:00Z"))
    assert apply_event(conn, late, now=NOW) == "stale"
    assert user(conn)["tier"] == "free"


def test_unknown_user_is_recorded_but_changes_nothing(conn):
    assert apply_event(conn, parse_paddle_event(payload(user_id="999")), now=NOW) == "ignored"
    assert apply_event(conn, parse_paddle_event(payload(user_id="999")), now=NOW) == "duplicate"
    assert conn.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0] == 0


def test_admin_tier_is_never_changed_by_billing(conn):
    conn.execute("UPDATE users SET is_admin=1, tier='premium' WHERE email='b@test.local'")
    conn.commit()
    apply_event(
        conn, parse_paddle_event(payload(status="canceled", etype="subscription.canceled")), now=NOW
    )
    assert user(conn)["tier"] == "premium"


def test_billing_event_stores_no_payload(conn):
    apply_event(conn, parse_paddle_event(payload()), now=NOW)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(billing_events)")]
    assert not {"payload", "body", "email"} & set(cols)


# --- routes -----------------------------------------------------------------------
@pytest.fixture
def client(conn, monkeypatch):
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 1,
        "email": "b@test.local",
        "tier": "free",
        "audience": "base",
        "is_admin": 0,
        "household_id": None,
    }
    monkeypatch.setattr(settings, "paddle_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "billing_enabled", True)
    yield TestClient(app)
    app.dependency_overrides.clear()


def post_webhook(client, body: dict, header: str | None = None, ts: int | None = None):
    raw = json.dumps(body).encode()
    h = header if header is not None else sign(raw, ts or int(datetime.now(UTC).timestamp()))
    return client.post(
        "/billing/webhook",
        content=raw,
        headers={"Paddle-Signature": h, "Content-Type": "application/json"},
    )


def test_webhook_disabled_returns_503(client, monkeypatch):
    monkeypatch.setattr(settings, "billing_enabled", False)
    assert post_webhook(client, payload()).status_code == 503


def test_webhook_rejects_bad_signature(client, conn):
    assert post_webhook(client, payload(), header="ts=1;h1=00").status_code == 400
    assert user(conn)["tier"] == "free"


def test_webhook_applies_and_dedups(client, conn):
    assert post_webhook(client, payload()).status_code == 200
    assert user(conn)["tier"] == "premium"
    r = post_webhook(client, payload())
    assert r.status_code == 200 and r.json()["result"] == "duplicate"


def test_webhook_ignores_unsupported_event_with_200(client):
    r = post_webhook(client, {"event_id": "e", "event_type": "transaction.completed", "data": {}})
    assert r.status_code == 200 and r.json()["result"] == "ignored"


def test_status_endpoint(client):
    post_webhook(client, payload())
    body = client.get("/billing/status").json()
    assert body["enabled"] is True
    assert body["subscription"]["status"] == "active"
    assert "provider_customer_id" not in body["subscription"]


def test_checkout_uses_provider_and_never_trusts_client_price(client):
    r = client.post("/billing/checkout-session", json={"plan": "premium_monthly"})
    assert r.status_code == 200 and r.json()["url"].startswith("https://billing.invalid/")
    assert client.post("/billing/checkout-session", json={"plan": "../../evil"}).status_code == 422


def test_checkout_disabled_returns_503(client, monkeypatch):
    monkeypatch.setattr(settings, "billing_enabled", False)
    assert (
        client.post("/billing/checkout-session", json={"plan": "premium_monthly"}).status_code
        == 503
    )


# --- multi-subscription tier + past_due sweep -----------------------------------
def test_second_subscription_keeps_premium_when_first_cancels(conn):
    apply_event(conn, parse_paddle_event(payload(sub="sub_1")), now=NOW)
    apply_event(conn, parse_paddle_event(payload(event_id="evt_b", sub="sub_2")), now=NOW)
    cancel = payload(
        event_id="evt_c",
        etype="subscription.canceled",
        status="canceled",
        sub="sub_1",
        occurred="2026-11-02T10:00:00Z",
    )
    apply_event(conn, parse_paddle_event(cancel), now=NOW)
    assert user(conn)["tier"] == "premium"


def test_sweep_downgrades_expired_past_due(conn):
    ev = payload(status="past_due", etype="subscription.past_due", occurred="2026-11-01T10:00:00Z")
    apply_event(conn, parse_paddle_event(ev), now=NOW)
    assert user(conn)["tier"] == "premium"  # inside grace
    assert sweep_expired(conn, now=NOW + timedelta(days=8), grace_days=7) == 1
    assert user(conn)["tier"] == "free"
    assert sweep_expired(conn, now=NOW + timedelta(days=9), grace_days=7) == 0


def test_sweep_leaves_in_grace_and_active_alone(conn):
    apply_event(conn, parse_paddle_event(payload()), now=NOW)
    assert sweep_expired(conn, now=NOW + timedelta(days=30), grace_days=7) == 0
    assert user(conn)["tier"] == "premium"


def test_sweep_skips_admins(conn):
    ev = payload(status="past_due", etype="subscription.past_due")
    apply_event(conn, parse_paddle_event(ev), now=NOW)
    conn.execute("UPDATE users SET is_admin=1, tier='premium'")
    conn.commit()
    sweep_expired(conn, now=NOW + timedelta(days=30), grace_days=7)
    assert user(conn)["tier"] == "premium"


# --- GDPR: erasure and portability -------------------------------------------------
def test_delete_user_erases_subscriptions(conn):
    apply_event(conn, parse_paddle_event(payload()), now=NOW)
    other = repo.create_user(conn, email="o@test.local", name="O", password_hash="x")
    apply_event(
        conn,
        parse_paddle_event(payload(event_id="evt_o", sub="sub_o", user_id=str(other["id"]))),
        now=NOW,
    )
    repo.delete_user(conn, 1)
    rows = conn.execute("SELECT user_id FROM subscriptions").fetchall()
    assert [r["user_id"] for r in rows] == [other["id"]]


def test_account_export_includes_billing(client):
    post_webhook(client, payload())
    # export contacts the other apps over HTTP; unreachable here, so only the foroba section matters
    body = client.get("/auth/account/export").json()
    sub = body["foroba"]["subscriptions"]
    assert sub[0]["status"] == "active"
    assert "provider_customer_id" in sub[0]
