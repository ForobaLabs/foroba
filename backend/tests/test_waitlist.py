"""Waitlist (Plan D, S1): table, service, public routes."""

from __future__ import annotations

import db


def _memory_conn():
    return db.connect(":memory:")


def test_waitlist_table_exists_with_expected_columns():
    conn = _memory_conn()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(waitlist)")}
    assert cols == {
        "id", "email", "apps", "lang", "consent_at",
        "confirm_token_hash", "confirmed_at", "created_at",
    }
