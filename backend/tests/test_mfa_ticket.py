"""PB-014: the second login factor must be bound to a password-verified MFA ticket.

Without it, /login/2fa, /login/recovery-code, /login/email-otp/send and /token/2fa
accepted an email alone, so the password step could be skipped entirely."""

import sqlite3

import jwt
import pyotp
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import config
from auth import keys
from auth import repository as repo
from auth.conn import get_conn
from auth.mfa_ticket import MfaTicketError, issue_mfa_ticket, verify_mfa_ticket
from auth.router import router as auth_router
from auth.security import decode_token
from auth.token_router import router as token_router
from db import init_schema, seed_mock_users
from rate_limit import limiter
from recovery_codes import generate_and_store

_SECRET = "JBSWY3DPEHPK3PXP"
_DEMO = {"email": "demo@foroba.app", "password": "Demo!2026"}


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def ctx(monkeypatch):
    monkeypatch.setattr(config.settings, "auth_2fa_enabled", True, raising=False)
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    seed_mock_users(conn)
    demo = repo.get_user_by_email(conn, _DEMO["email"])
    repo.set_totp_secret(conn, demo["id"], _SECRET)
    repo.enable_totp(conn, demo["id"])
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(auth_router)
    app.include_router(token_router)
    return TestClient(app), conn


def _code() -> str:
    return pyotp.TOTP(_SECRET).now()


def _login_ticket(c: TestClient) -> str:
    r = c.post("/auth/login", json=_DEMO)
    assert r.status_code == 200
    body = r.json()
    assert body["mfa_required"] is True
    assert body["mfa_ticket"]
    return body["mfa_ticket"]


def test_login_sets_short_lived_httponly_ticket_cookie(ctx):
    c, _ = ctx
    r = c.post("/auth/login", json=_DEMO)
    header = r.headers["set-cookie"].lower()
    assert "mfa_ticket=" in header
    assert "httponly" in header
    assert "samesite=strict" in header
    assert "max-age=300" in header


def test_login_2fa_without_ticket_is_rejected(ctx):
    c, _ = ctx
    r = c.post("/auth/login/2fa", json={"email": _DEMO["email"], "code": _code()})
    assert r.status_code == 401
    assert not c.cookies.get("suite_session")


def test_login_2fa_with_body_ticket_succeeds(ctx):
    c, _ = ctx
    ticket = _login_ticket(c)
    c.cookies.clear()
    r = c.post(
        "/auth/login/2fa",
        json={"email": _DEMO["email"], "code": _code(), "mfa_ticket": ticket},
    )
    assert r.status_code == 200
    assert c.cookies.get("suite_session")


def test_login_2fa_with_cookie_ticket_succeeds_and_clears_it(ctx):
    c, _ = ctx
    _login_ticket(c)
    r = c.post("/auth/login/2fa", json={"email": _DEMO["email"], "code": _code()})
    assert r.status_code == 200
    assert c.cookies.get("suite_session")
    assert not c.cookies.get("mfa_ticket")


def test_ticket_for_another_user_is_rejected(ctx):
    c, conn = ctx
    pro = repo.get_user_by_email(conn, "pro@foroba.app")
    ticket = issue_mfa_ticket(pro["id"], pro.get("session_version", 1))
    r = c.post(
        "/auth/login/2fa",
        json={"email": _DEMO["email"], "code": _code(), "mfa_ticket": ticket},
    )
    assert r.status_code == 401


def test_ticket_is_void_after_session_version_bump(ctx):
    c, conn = ctx
    ticket = _login_ticket(c)
    c.cookies.clear()
    conn.execute(
        "UPDATE users SET session_version = session_version + 1 WHERE email = ?",
        (_DEMO["email"],),
    )
    conn.commit()
    r = c.post(
        "/auth/login/2fa",
        json={"email": _DEMO["email"], "code": _code(), "mfa_ticket": ticket},
    )
    assert r.status_code == 401


def test_recovery_code_requires_ticket(ctx):
    c, conn = ctx
    demo = repo.get_user_by_email(conn, _DEMO["email"])
    codes = generate_and_store(conn, demo["id"])
    body = {"email": _DEMO["email"], "recovery_code": codes[0]}
    assert c.post("/auth/login/recovery-code", json=body).status_code == 401
    ticket = _login_ticket(c)
    c.cookies.clear()
    r = c.post("/auth/login/recovery-code", json={**body, "mfa_ticket": ticket})
    assert r.status_code == 200


def test_email_otp_send_requires_ticket(ctx):
    c, conn = ctx
    demo = repo.get_user_by_email(conn, _DEMO["email"])
    repo.enable_email_otp(conn, demo["id"])
    r = c.post("/auth/login/email-otp/send", json={"email": _DEMO["email"]})
    assert r.status_code == 401


def test_token_2fa_requires_ticket(ctx):
    c, _ = ctx
    base = {
        "email": _DEMO["email"],
        "code": _code(),
        "method": "totp",
        "device_label": "iPhone",
    }
    assert c.post("/auth/token/2fa", json=base).status_code == 401
    r = c.post(
        "/auth/token",
        json={**_DEMO, "device_label": "iPhone"},
    )
    assert r.status_code == 200
    ticket = r.json()["mfa_ticket"]
    assert "mfa_ticket" not in r.cookies
    c.cookies.set("mfa_ticket", ticket)  # a cookie alone never satisfies the native endpoint
    assert c.post("/auth/token/2fa", json=base).status_code == 401
    r = c.post("/auth/token/2fa", json={**base, "mfa_ticket": ticket})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_mfa_ticket_is_not_a_session_token(ctx):
    _, conn = ctx
    demo = repo.get_user_by_email(conn, _DEMO["email"])
    ticket = issue_mfa_ticket(demo["id"], demo.get("session_version", 1))
    _, public_key, _ = keys.get_keypair(config.settings)
    with pytest.raises(jwt.PyJWTError):
        decode_token(ticket, public_key)


def test_session_token_is_not_an_mfa_ticket(ctx):
    _, conn = ctx
    demo = repo.get_user_by_email(conn, _DEMO["email"])
    from auth.security import create_token

    private_key, _, kid = keys.get_keypair(config.settings)
    session = create_token(demo["id"], private_key, 5, kid=kid)
    with pytest.raises(MfaTicketError):
        verify_mfa_ticket(session, demo)
