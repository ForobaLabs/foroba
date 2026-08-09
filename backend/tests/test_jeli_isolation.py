"""CL-2.7 — Jeli sandbox per-user isolation regression test (foroba#249).

The DPIA identified AI sandbox cross-user data leakage as a risk.
Jeli stores sandbox conversations and user context in SQLite, scoped by user_id.
These tests verify that user A cannot read user B's sandbox history or context,
and that updating one user's context never affects another user's context.
"""

import sqlite3

from db import (
    get_sandbox_history,
    get_sandbox_user_context,
    init_schema,
    save_sandbox_turn,
    update_sandbox_user_context,
)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def test_sandbox_history_is_scoped_per_user():
    """user_a's sandbox history must not contain user_b's conversations."""
    conn = _conn()
    save_sandbox_turn(conn, "u1", "s1", "Alice question", "Alice answer")
    save_sandbox_turn(conn, "u2", "s2", "Bob secret question", "Bob secret answer")

    history_a = get_sandbox_history(conn, "u1", "s1")
    contents_a = [row["content"] for row in history_a]

    assert any("Alice question" in c for c in contents_a), "User A's own turn missing"
    assert not any("Bob secret" in c for c in contents_a), (
        "User B's conversation appeared in user A's sandbox history — isolation failure!"
    )


def test_sandbox_context_is_scoped_per_user():
    """Updating user_b's context must not affect user_a's context."""
    conn = _conn()
    update_sandbox_user_context(conn, "u1", "Alice context: heavy Pazuru user.")
    update_sandbox_user_context(conn, "u2", "Bob context: Tsumi power user.")

    ctx_a = get_sandbox_user_context(conn, "u1")
    ctx_b = get_sandbox_user_context(conn, "u2")

    assert "Alice context" in ctx_a
    assert "Bob context" not in ctx_a, (
        "User B's context leaked into user A's sandbox context — isolation failure!"
    )
    assert "Bob context" in ctx_b
    assert "Alice context" not in ctx_b


def test_sandbox_history_different_sessions_same_user_are_independent():
    """Two sessions for the same user must not bleed into each other."""
    conn = _conn()
    save_sandbox_turn(conn, "u1", "session-A", "session A question", "session A answer")
    save_sandbox_turn(conn, "u1", "session-B", "session B question", "session B answer")

    history_a = get_sandbox_history(conn, "u1", "session-A")
    contents_a = [row["content"] for row in history_a]
    assert not any("session B" in c for c in contents_a), (
        "Session B's messages appeared in session A's history"
    )


def test_empty_history_for_unknown_user():
    """A brand-new user with no conversations must get an empty history."""
    conn = _conn()
    save_sandbox_turn(conn, "u1", "s1", "only user", "only answer")

    history_new = get_sandbox_history(conn, "unknown-user-99", "s1")
    assert history_new == [], "Expected empty history for a user with no conversations"
