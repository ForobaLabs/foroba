import sqlite3

import pyotp
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import config
from auth import repository as repo
from auth.conn import get_conn
from auth.mfa_ticket import issue_mfa_ticket
from auth.router import router as auth_router
from db import init_schema, seed_mock_users
from rate_limit import limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


def _client(monkeypatch, flag: bool):
    monkeypatch.setattr(config.settings, "auth_2fa_enabled", flag, raising=False)
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    seed_mock_users(conn)
    # Enable 2FA for demo user
    secret = "JBSWY3DPEHPK3PXP"
    demo = repo.get_user_by_email(conn, "demo@foroba.app")
    repo.set_totp_secret(conn, demo["id"], secret)
    repo.enable_totp(conn, demo["id"])
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(auth_router)
    return TestClient(app), secret


def test_login_challenges_when_flag_on(monkeypatch):
    c, secret = _client(monkeypatch, True)
    r = c.post("/auth/login", json={"email": "demo@foroba.app", "password": "Demo!2026"})
    assert r.status_code == 200
    assert r.json().get("mfa_required") is True
    assert not c.cookies.get("suite_session")  # no session yet
    code = pyotp.TOTP(secret).now()
    r2 = c.post("/auth/login/2fa", json={"email": "demo@foroba.app", "code": code})
    assert r2.status_code == 200
    assert c.cookies.get("suite_session")


def test_login_ignores_2fa_when_flag_off(monkeypatch):
    c, _ = _client(monkeypatch, False)
    r = c.post("/auth/login", json={"email": "demo@foroba.app", "password": "Demo!2026"})
    assert r.status_code == 200
    assert r.json().get("mfa_required") in (None, False)
    assert c.cookies.get("suite_session")  # logged in directly


def test_disabled_account_rejected_before_2fa_step(monkeypatch):
    c, _secret = _client(monkeypatch, True)
    conn = c.app.dependency_overrides[get_conn]()
    demo = repo.get_user_by_email(conn, "demo@foroba.app")
    repo.set_account_disabled(conn, demo["id"], True)

    r = c.post("/auth/login", json={"email": "demo@foroba.app", "password": "Demo!2026"})
    assert r.status_code == 403


def test_2fa_endpoint_rejects_disabled_account_directly(monkeypatch):
    """Defense in depth: /login/2fa also rejects disabled accounts, even with a ticket
    issued before the account was disabled."""
    c, secret = _client(monkeypatch, True)
    conn = c.app.dependency_overrides[get_conn]()
    demo = repo.get_user_by_email(conn, "demo@foroba.app")
    ticket = issue_mfa_ticket(demo["id"], demo.get("session_version", 1))
    repo.set_account_disabled(conn, demo["id"], True)

    code = pyotp.TOTP(secret).now()
    r = c.post(
        "/auth/login/2fa",
        json={"email": "demo@foroba.app", "code": code, "mfa_ticket": ticket},
    )
    assert r.status_code == 403


def test_login_challenges_lists_all_enabled_methods(monkeypatch):
    c, _secret = _client(monkeypatch, True)
    conn = c.app.dependency_overrides[get_conn]()
    demo = repo.get_user_by_email(conn, "demo@foroba.app")
    repo.enable_email_otp(conn, demo["id"])
    r = c.post("/auth/login", json={"email": "demo@foroba.app", "password": "Demo!2026"})
    assert r.status_code == 200
    assert set(r.json()["methods"]) == {"totp", "email_otp"}


def test_login_2fa_dispatches_to_email_otp(monkeypatch):
    c, _secret = _client(monkeypatch, True)
    conn = c.app.dependency_overrides[get_conn]()
    demo = repo.get_user_by_email(conn, "demo@foroba.app")
    from config import settings

    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "localhost")
    monkeypatch.setattr(settings, "smtp_from", "noreply@example.com")
    sent = {}
    monkeypatch.setattr(
        "email_otp.send_otp_email", lambda to, code, **kw: sent.update(code=code)
    )
    repo.enable_email_otp(conn, demo["id"])
    from email_otp import generate_and_send

    generate_and_send(conn, demo["id"], demo["email"])
    code = sent["code"]
    r = c.post(
        "/auth/login/2fa",
        json={
            "email": "demo@foroba.app",
            "code": code,
            "method": "email_otp",
            "mfa_ticket": issue_mfa_ticket(demo["id"], demo.get("session_version", 1)),
        },
    )
    assert r.status_code == 200
    assert c.cookies.get("suite_session")
