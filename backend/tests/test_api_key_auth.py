"""Tests for require_api_key: key verification, entitlement gating, last_used tracking
(foroba#165, TI-D item 5, Plan A)."""

from __future__ import annotations

import sqlite3
from typing import ClassVar

import pytest
from fastapi import HTTPException

import db
from auth.api_key_auth import require_api_key
from auth.security import hash_password
from settings_store import init_settings, set_value


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_schema(c)
    init_settings(c)
    set_value(c, "premium_gating_enabled", "true")
    return c


def _seed_user(conn, *, tier="premium", audience="base") -> int:
    cur = conn.execute(
        "INSERT INTO users (email, name, password_hash, tier, audience) VALUES (?, ?, ?, ?, ?)",
        (f"{tier}-{audience}@test.local", "U", "x", tier, audience),
    )
    conn.commit()
    return cur.lastrowid


def _seed_key(conn, user_id: int, *, is_active: bool = True) -> tuple[str, str]:
    secret = "s3cr3t-test-value"
    prefix = "fpk_testprefix"
    db.create_api_key(
        conn, user_id=user_id, label="test", key_prefix=prefix, secret_hash=hash_password(secret)
    )
    if not is_active:
        row = db.get_api_key_by_prefix(conn, prefix)
        db.revoke_api_key(conn, row["id"], user_id=user_id)
    return prefix, secret


def test_valid_key_returns_user_and_updates_last_used(conn):
    user_id = _seed_user(conn)
    prefix, secret = _seed_key(conn, user_id)

    user = require_api_key(authorization=f"Bearer {prefix}.{secret}", conn=conn)

    assert user["id"] == user_id
    row = db.get_api_key_by_prefix(conn, prefix)
    assert row["last_used_at"] is not None


def test_missing_header_is_401(conn):
    with pytest.raises(HTTPException) as exc_info:
        require_api_key(authorization=None, conn=conn)
    assert exc_info.value.status_code == 401


def test_malformed_header_is_401(conn):
    with pytest.raises(HTTPException) as exc_info:
        require_api_key(authorization="not-a-bearer-token", conn=conn)
    assert exc_info.value.status_code == 401


def test_unknown_prefix_is_401(conn):
    with pytest.raises(HTTPException) as exc_info:
        require_api_key(authorization="Bearer fpk_unknown.somesecret", conn=conn)
    assert exc_info.value.status_code == 401


def test_wrong_secret_is_401(conn):
    user_id = _seed_user(conn)
    prefix, _ = _seed_key(conn, user_id)
    with pytest.raises(HTTPException) as exc_info:
        require_api_key(authorization=f"Bearer {prefix}.wrongsecret", conn=conn)
    assert exc_info.value.status_code == 401


def test_revoked_key_is_401(conn):
    user_id = _seed_user(conn)
    prefix, secret = _seed_key(conn, user_id, is_active=False)
    with pytest.raises(HTTPException) as exc_info:
        require_api_key(authorization=f"Bearer {prefix}.{secret}", conn=conn)
    assert exc_info.value.status_code == 401


def test_free_tier_user_gets_402(conn):
    user_id = _seed_user(conn, tier="free")
    prefix, secret = _seed_key(conn, user_id)
    with pytest.raises(HTTPException) as exc_info:
        require_api_key(authorization=f"Bearer {prefix}.{secret}", conn=conn)
    assert exc_info.value.status_code == 402


def test_api_key_rate_limit_key_uses_prefix():
    from auth.api_key_auth import api_key_rate_limit_key

    class _FakeRequest:
        headers: ClassVar = {"authorization": "Bearer fpk_abc123.somesecret"}

    assert api_key_rate_limit_key(_FakeRequest()) == "fpk_abc123"


def test_api_key_rate_limit_key_falls_back_to_anonymous():
    from auth.api_key_auth import api_key_rate_limit_key

    class _FakeRequest:
        headers: ClassVar[dict] = {}

    assert api_key_rate_limit_key(_FakeRequest()) == "anonymous"
