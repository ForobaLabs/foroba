"""Tests for purge_mock_users (foroba#254) — hosted-mode dev-seed cleanup."""

from __future__ import annotations

import sqlite3

import pytest

from db import _SEED_ONLY_EMAILS, init_schema, purge_mock_users, seed_mock_users


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    init_schema(c)
    return c


def _count(conn: sqlite3.Connection, email: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM users WHERE email = ?", (email,)).fetchone()[0]


def test_purge_removes_dev_seed_accounts(conn):
    """purge_mock_users must delete demo/pro/test but NOT admin."""
    seed_mock_users(conn)
    removed = purge_mock_users(conn)
    assert set(removed) == set(_SEED_ONLY_EMAILS)
    for email in _SEED_ONLY_EMAILS:
        assert _count(conn, email) == 0, f"{email} should have been purged"
    # admin survives
    assert _count(conn, "admin@foroba.app") == 1


def test_purge_is_idempotent(conn):
    """Calling purge twice returns empty list the second time; no crash."""
    seed_mock_users(conn)
    purge_mock_users(conn)
    removed_again = purge_mock_users(conn)
    assert removed_again == []


def test_purge_on_empty_db_is_safe(conn):
    """purge_mock_users on a DB with no seed rows returns empty list."""
    removed = purge_mock_users(conn)
    assert removed == []


def test_purge_leaves_real_users_untouched(conn):
    """purge_mock_users must not touch accounts that don't match the seed list."""
    from auth.security import hash_password

    conn.execute(
        "INSERT INTO users (email, name, password_hash, tier, audience) "
        "VALUES (?, ?, ?, ?, ?)",
        ("alice@example.com", "Alice", hash_password("pw"), "free", "base"),
    )
    conn.commit()
    seed_mock_users(conn)
    purge_mock_users(conn)
    assert _count(conn, "alice@example.com") == 1
