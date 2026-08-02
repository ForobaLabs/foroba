import sqlite3

from db import init_schema
from passkeys.service import (
    consume_challenge,
    registration_options_for_user,
    store_challenge,
)


def _conn_with_user() -> tuple[sqlite3.Connection, int]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    conn.execute(
        "INSERT INTO users (email, password_hash, name) VALUES ('w@example.com', 'h', 'W')"
    )
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE email = 'w@example.com'").fetchone()["id"]
    return conn, user_id


def test_registration_options_returns_json_with_challenge():
    conn, user_id = _conn_with_user()
    options_json = registration_options_for_user(conn, user_id, "w@example.com")
    assert "challenge" in options_json
    row = conn.execute(
        "SELECT challenge, purpose FROM webauthn_challenges WHERE user_id = ?", (user_id,)
    ).fetchone()
    assert row["purpose"] == "registration"


def test_store_and_consume_challenge_round_trip():
    conn, user_id = _conn_with_user()
    store_challenge(conn, user_id, "abc123", purpose="authentication")
    challenge = consume_challenge(conn, user_id, purpose="authentication")
    assert challenge == "abc123"
    # single-use: gone after consuming
    assert consume_challenge(conn, user_id, purpose="authentication") is None
