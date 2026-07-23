"""Unit tests for api_keys/webhooks/webhook_deliveries CRUD helpers (foroba#165,
TI-D item 5, Plan A)."""
from __future__ import annotations

import sqlite3

import pytest

import db


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_schema(c)
    return c


def test_create_and_get_api_key_by_prefix(conn):
    row = db.create_api_key(conn, user_id=1, label="test", key_prefix="fpk_abc", secret_hash="hash")
    assert row["label"] == "test"
    assert row["is_active"] == 1
    assert row["last_used_at"] is None

    found = db.get_api_key_by_prefix(conn, "fpk_abc")
    assert found["id"] == row["id"]
    assert db.get_api_key_by_prefix(conn, "fpk_unknown") is None


def test_list_api_keys_scoped_to_user(conn):
    db.create_api_key(conn, user_id=1, label="a", key_prefix="fpk_a", secret_hash="h")
    db.create_api_key(conn, user_id=2, label="b", key_prefix="fpk_b", secret_hash="h")
    assert [r["label"] for r in db.list_api_keys(conn, user_id=1)] == ["a"]


def test_revoke_api_key_soft_deletes(conn):
    row = db.create_api_key(conn, user_id=1, label="a", key_prefix="fpk_a", secret_hash="h")
    assert db.revoke_api_key(conn, row["id"], user_id=1) is True
    assert db.get_api_key_by_prefix(conn, "fpk_a")["is_active"] == 0
    assert db.revoke_api_key(conn, 999, user_id=1) is False


def test_touch_api_key_last_used_sets_timestamp(conn):
    row = db.create_api_key(conn, user_id=1, label="a", key_prefix="fpk_a", secret_hash="h")
    db.touch_api_key_last_used(conn, row["id"])
    assert db.get_api_key_by_prefix(conn, "fpk_a")["last_used_at"] is not None


def test_webhook_crud_roundtrip(conn):
    row = db.create_webhook(conn, user_id=1, target_url="https://x.test/hook", signing_secret="sec")
    assert row["is_active"] == 1
    assert row["consecutive_failures"] == 0

    assert [w["id"] for w in db.list_webhooks(conn, user_id=1)] == [row["id"]]
    assert db.list_active_webhooks(conn)[0]["id"] == row["id"]

    assert db.delete_webhook(conn, row["id"], user_id=1) is True
    assert db.get_webhook(conn, row["id"], user_id=1) is None


def test_register_webhook_failure_auto_disables_at_ten(conn):
    row = db.create_webhook(conn, user_id=1, target_url="https://x.test/hook", signing_secret="sec")
    for _ in range(9):
        updated = db.register_webhook_failure(conn, row["id"])
        assert updated["is_active"] == 1
    updated = db.register_webhook_failure(conn, row["id"])
    assert updated["consecutive_failures"] == 10
    assert updated["is_active"] == 0
    assert updated["disabled_at"] is not None


def test_reactivate_webhook_resets_failure_state(conn):
    row = db.create_webhook(conn, user_id=1, target_url="https://x.test/hook", signing_secret="sec")
    for _ in range(10):
        db.register_webhook_failure(conn, row["id"])
    reactivated = db.reactivate_webhook(conn, row["id"], user_id=1)
    assert reactivated["is_active"] == 1
    assert reactivated["consecutive_failures"] == 0
    assert reactivated["disabled_at"] is None
    assert db.reactivate_webhook(conn, 999, user_id=1) is None


def test_webhook_delivery_dedup_and_attempt_tracking(conn):
    webhook = db.create_webhook(conn, user_id=1, target_url="https://x.test/hook", signing_secret="sec")
    assert db.get_webhook_delivery(conn, webhook["id"], "goal_reached:1") is None

    db.upsert_webhook_delivery_attempt(conn, webhook["id"], "goal_reached:1", attempt_count=1, status="pending")
    row = db.get_webhook_delivery(conn, webhook["id"], "goal_reached:1")
    assert row["attempt_count"] == 1
    assert row["last_status"] == "pending"

    db.upsert_webhook_delivery_success(conn, webhook["id"], "goal_reached:1", 2)
    row = db.get_webhook_delivery(conn, webhook["id"], "goal_reached:1")
    assert row["last_status"] == "success"
    assert row["attempt_count"] == 2
    assert row["delivered_at"] is not None
