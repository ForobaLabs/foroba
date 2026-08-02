import sqlite3

from db import init_schema


def _fresh_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def test_recovery_codes_table_exists():
    conn = _fresh_conn()
    conn.execute("INSERT INTO recovery_codes (user_id, code_hash) VALUES (1, 'x')")
    row = conn.execute("SELECT user_id, code_hash, used_at FROM recovery_codes").fetchone()
    assert row["user_id"] == 1
    assert row["used_at"] is None


def test_email_otp_codes_table_exists():
    conn = _fresh_conn()
    conn.execute(
        "INSERT INTO email_otp_codes (user_id, code_hash, expires_at) "
        "VALUES (1, 'x', '2026-01-01T00:00:00')"
    )
    row = conn.execute("SELECT user_id FROM email_otp_codes").fetchone()
    assert row["user_id"] == 1


def test_webauthn_credentials_table_exists():
    conn = _fresh_conn()
    conn.execute(
        "INSERT INTO webauthn_credentials (user_id, credential_id, public_key) "
        "VALUES (1, 'cred-1', 'pubkey')"
    )
    row = conn.execute("SELECT sign_count FROM webauthn_credentials").fetchone()
    assert row["sign_count"] == 0


def test_webauthn_challenges_table_exists():
    conn = _fresh_conn()
    conn.execute(
        "INSERT INTO webauthn_challenges (user_id, challenge, purpose) "
        "VALUES (1, 'chal', 'registration')"
    )
    row = conn.execute("SELECT purpose FROM webauthn_challenges").fetchone()
    assert row["purpose"] == "registration"


def test_users_has_email_otp_and_webauthn_flags():
    conn = _fresh_conn()
    conn.execute(
        "INSERT INTO users (email, password_hash, name) VALUES ('t@example.com', 'h', 'T')"
    )
    row = conn.execute(
        "SELECT email_otp_enabled, webauthn_enabled FROM users WHERE email = 't@example.com'"
    ).fetchone()
    assert row["email_otp_enabled"] == 0
    assert row["webauthn_enabled"] == 0
