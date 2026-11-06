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


# ── Pre-beta Task 2.2 row 4: short-lived, single outstanding, attempt-capped codes ──


def _issue(monkeypatch, conn, user_id) -> str:
    from config import settings

    monkeypatch.setattr(settings, "smtp_enabled", True)
    sent = {}
    monkeypatch.setattr(
        "email_otp.send_otp_email",
        lambda to, code, *, country=None, ttl_minutes=None: sent.update(code=code, ttl=ttl_minutes),
    )
    generate_and_send(conn, user_id, "o@example.com")
    return sent["code"], sent["ttl"]


def test_code_expires_within_30_minutes(monkeypatch):
    conn, user_id = _conn_with_user()
    _, ttl = _issue(monkeypatch, conn, user_id)
    assert ttl <= 30
    expires = conn.execute("SELECT expires_at FROM email_otp_codes").fetchone()["expires_at"]
    assert datetime.fromisoformat(expires) <= datetime.now(UTC) + timedelta(minutes=30, seconds=5)


def test_new_code_supersedes_outstanding_ones(monkeypatch):
    conn, user_id = _conn_with_user()
    old, _ = _issue(monkeypatch, conn, user_id)
    new, _ = _issue(monkeypatch, conn, user_id)
    if old == new:
        pytest.skip("1-in-a-million identical codes")
    assert not verify_and_consume(conn, user_id, old)
    assert verify_and_consume(conn, user_id, new)


def test_five_wrong_attempts_void_the_code(monkeypatch):
    conn, user_id = _conn_with_user()
    code, _ = _issue(monkeypatch, conn, user_id)
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    for _ in range(5):
        assert not verify_and_consume(conn, user_id, wrong)
    assert not verify_and_consume(conn, user_id, code)


def test_a_typo_does_not_void_the_code(monkeypatch):
    conn, user_id = _conn_with_user()
    code, _ = _issue(monkeypatch, conn, user_id)
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    assert not verify_and_consume(conn, user_id, wrong)
    assert verify_and_consume(conn, user_id, code)
