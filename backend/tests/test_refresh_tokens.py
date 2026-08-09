import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from auth import refresh_tokens as rt
from db import init_schema


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_schema(c)
    c.execute(
        "INSERT INTO users (id, email, name, password_hash) VALUES (1, 'a@b.c', 'Test', 'x')"
    )
    c.commit()
    return c


def test_issue_returns_plaintext_and_stores_only_a_hash(conn):
    token = rt.issue(conn, 1, "iPhone")
    assert len(token) >= 40
    stored = conn.execute(
        "SELECT token_hash FROM refresh_tokens"
    ).fetchone()["token_hash"]
    assert stored != token


def test_rotate_returns_a_new_token_and_revokes_the_old_one(conn):
    first = rt.issue(conn, 1, "iPhone")
    second, row = rt.rotate(conn, first)
    assert second != first
    assert row["user_id"] == 1
    revoked = conn.execute(
        "SELECT revoked_at FROM refresh_tokens WHERE revoked_at IS NOT NULL"
    ).fetchall()
    assert len(revoked) == 1


def test_rotate_keeps_the_family_id(conn):
    first = rt.issue(conn, 1, "iPhone")
    second, _ = rt.rotate(conn, first)
    families = {
        r["family_id"]
        for r in conn.execute("SELECT family_id FROM refresh_tokens")
    }
    assert len(families) == 1
    rt.rotate(conn, second)
    families = {
        r["family_id"]
        for r in conn.execute("SELECT family_id FROM refresh_tokens")
    }
    assert len(families) == 1


def test_reusing_a_rotated_token_revokes_the_whole_family(conn):
    first = rt.issue(conn, 1, "iPhone")
    second, _ = rt.rotate(conn, first)
    with pytest.raises(rt.ReuseDetected):
        rt.rotate(conn, first)
    live = conn.execute(
        "SELECT COUNT(*) AS n FROM refresh_tokens WHERE revoked_at IS NULL"
    ).fetchone()["n"]
    assert live == 0
    with pytest.raises(rt.InvalidRefreshToken):
        rt.rotate(conn, second)


def test_rotate_rejects_an_unknown_token(conn):
    with pytest.raises(rt.InvalidRefreshToken):
        rt.rotate(conn, "not-a-real-token")


def test_rotate_rejects_an_expired_token(conn):
    token = rt.issue(conn, 1, "iPhone")
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    conn.execute("UPDATE refresh_tokens SET expires_at = ?", (past,))
    conn.commit()
    with pytest.raises(rt.InvalidRefreshToken):
        rt.rotate(conn, token)


def test_revoke_all_for_user_kills_every_session(conn):
    rt.issue(conn, 1, "iPhone")
    rt.issue(conn, 1, "iPad")
    rt.revoke_all_for_user(conn, 1)
    live = conn.execute(
        "SELECT COUNT(*) AS n FROM refresh_tokens WHERE revoked_at IS NULL"
    ).fetchone()["n"]
    assert live == 0


def test_list_sessions_returns_only_live_ones_without_hashes(conn):
    rt.issue(conn, 1, "iPhone")
    dead = rt.issue(conn, 1, "iPad")
    rt.revoke(conn, dead)
    sessions = rt.list_sessions(conn, 1)
    assert [s["device_label"] for s in sessions] == ["iPhone"]
    assert "token_hash" not in sessions[0]
