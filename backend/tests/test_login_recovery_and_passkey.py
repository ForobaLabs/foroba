import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import repository as repo
from auth.conn import get_conn
from auth.mfa_ticket import issue_mfa_ticket
from auth.router import router as auth_router
from db import init_schema, seed_mock_users
from rate_limit import limiter
from recovery_codes import generate_and_store


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


def _client() -> tuple[TestClient, sqlite3.Connection]:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    seed_mock_users(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(auth_router)
    return TestClient(app), conn


def _ticket(conn: sqlite3.Connection, email: str = "demo@foroba.app") -> str:
    user = repo.get_user_by_email(conn, email)
    return issue_mfa_ticket(user["id"], user.get("session_version", 1))


def test_login_with_recovery_code_succeeds_and_consumes_it():
    c, conn = _client()
    demo = repo.get_user_by_email(conn, "demo@foroba.app")
    repo.enable_totp(conn, demo["id"])
    codes = generate_and_store(conn, demo["id"])
    r = c.post(
        "/auth/login/recovery-code",
        json={
            "email": "demo@foroba.app",
            "recovery_code": codes[0],
            "mfa_ticket": _ticket(conn),
        },
    )
    assert r.status_code == 200
    assert c.cookies.get("suite_session")
    r2 = c.post(
        "/auth/login/recovery-code",
        json={
            "email": "demo@foroba.app",
            "recovery_code": codes[0],
            "mfa_ticket": _ticket(conn),
        },
    )
    assert r2.status_code == 401  # single-use


def test_login_with_invalid_recovery_code_rejected():
    c, conn = _client()
    demo = repo.get_user_by_email(conn, "demo@foroba.app")
    repo.enable_totp(conn, demo["id"])
    generate_and_store(conn, demo["id"])
    r = c.post(
        "/auth/login/recovery-code",
        json={
            "email": "demo@foroba.app",
            "recovery_code": "NOTVALID12",
            "mfa_ticket": _ticket(conn),
        },
    )
    assert r.status_code == 401


def test_login_email_otp_send_works_before_authentication(monkeypatch):
    from config import settings

    c, conn = _client()
    demo = repo.get_user_by_email(conn, "demo@foroba.app")
    repo.enable_email_otp(conn, demo["id"])
    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "localhost")
    monkeypatch.setattr(settings, "smtp_from", "noreply@example.com")
    sent = {}
    monkeypatch.setattr(
        "email_otp.send_otp_email", lambda to, code, **kw: sent.update(code=code)
    )
    r = c.post(
        "/auth/login/email-otp/send",
        json={"email": "demo@foroba.app", "mfa_ticket": _ticket(conn)},
    )
    assert r.status_code == 200
    assert r.json() == {"sent": True}
    assert "code" in sent


def test_login_email_otp_send_rejects_when_not_enrolled():
    c, conn = _client()
    r = c.post(
        "/auth/login/email-otp/send",
        json={"email": "demo@foroba.app", "mfa_ticket": _ticket(conn)},
    )
    assert r.status_code == 400
