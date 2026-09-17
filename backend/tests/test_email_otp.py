import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from db import init_schema
from email_otp import EmailNotConfiguredError, generate_and_send, verify_and_consume


def _conn_with_user() -> tuple[sqlite3.Connection, int]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    conn.execute(
        "INSERT INTO users (email, password_hash, name) VALUES ('o@example.com', 'h', 'O')"
    )
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE email = 'o@example.com'").fetchone()["id"]
    return conn, user_id


def test_generate_and_send_requires_smtp_enabled(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "smtp_enabled", False)
    conn, user_id = _conn_with_user()
    with pytest.raises(EmailNotConfiguredError):
        generate_and_send(conn, user_id, "o@example.com")


def test_generate_and_send_then_verify(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "localhost")
    monkeypatch.setattr(settings, "smtp_from", "noreply@example.com")
    sent = {}

    def fake_send_otp_email(to, code, *, country=None, ttl_minutes=None):
        sent["to"] = to
        sent["code"] = code

    monkeypatch.setattr("email_otp.send_otp_email", fake_send_otp_email)
    conn, user_id = _conn_with_user()
    generate_and_send(conn, user_id, "o@example.com")
    assert sent["to"] == "o@example.com"
    code = sent["code"]
    assert verify_and_consume(conn, user_id, code) is True
    assert verify_and_consume(conn, user_id, code) is False  # single-use


def test_verify_rejects_expired_code(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "localhost")
    monkeypatch.setattr(settings, "smtp_from", "noreply@example.com")
    monkeypatch.setattr("email_otp.send_otp_email", lambda to, code, **kw: None)
    conn, user_id = _conn_with_user()
    generate_and_send(conn, user_id, "o@example.com")
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    conn.execute("UPDATE email_otp_codes SET expires_at = ? WHERE user_id = ?", (past, user_id))
    conn.commit()
    assert verify_and_consume(conn, user_id, "000000") is False
