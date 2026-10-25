import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.conn import get_conn
from auth.router import router as auth_router
from db import init_schema, seed_mock_users
from rate_limit import limiter
from settings_store import init_settings
from stepup_router import router as stepup_router
from twofa.router import router as twofa_router


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    init_settings(conn)
    seed_mock_users(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(auth_router)
    app.include_router(twofa_router)
    app.include_router(stepup_router)
    return TestClient(app)


def test_stepup_verify_requires_auth(client):
    resp = client.post(
        "/auth/stepup/verify", json={"app": "pazuru", "method": "totp", "code": "000000"}
    )
    assert resp.status_code == 401


def test_stepup_verify_with_totp_sets_app_cookie(client):
    import pyotp

    client.post(
        "/auth/register",
        json={
            "email": "stepupuser@example.com",
            "email_confirm": "stepupuser@example.com",
            "name": "Step Up",
            "password": "Sup3rSecret!",
            "password_confirm": "Sup3rSecret!",
            "tos_accepted": True,
        },
    )
    enroll_resp = client.post("/auth/2fa/enroll")
    secret = enroll_resp.json()["secret"]
    code = pyotp.TOTP(secret).now()
    client.post("/auth/2fa/verify", json={"code": code})
    code2 = pyotp.TOTP(secret).now()
    resp = client.post(
        "/auth/stepup/verify", json={"app": "pazuru", "method": "totp", "code": code2}
    )
    assert resp.status_code == 200
    assert client.cookies.get("stepup_pazuru")


def _refresh(client, token, internal=True):
    from config import settings

    headers = {"X-Internal-Token": settings.internal_api_token} if internal else {}
    return client.post(
        "/auth/stepup/refresh", json={"app": "pazuru", "token": token}, headers=headers
    )


@pytest.fixture
def internal_token(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "internal_api_token", "t" * 32)


def test_stepup_refresh_rejects_expired_token(client, monkeypatch, internal_token):
    from config import settings

    monkeypatch.setattr(settings, "stepup_ttl_minutes", 0)
    from stepup import issue_stepup_token

    token = issue_stepup_token(user_id=1, app="pazuru")
    assert _refresh(client, token).status_code == 401


def test_stepup_refresh_extends_a_valid_token(client, internal_token):
    from stepup import issue_stepup_token, verify_stepup_token

    token = issue_stepup_token(user_id=1, app="pazuru")
    resp = _refresh(client, token)
    assert resp.status_code == 200
    new_token = resp.json()["token"]
    claims = verify_stepup_token(new_token, expected_app="pazuru")
    assert claims["sub"] == "1"


# Plan AU M-1: refresh is server-to-server only, capped, and honours the session floor.
def test_refresh_requires_internal_token(client, internal_token):
    from stepup import issue_stepup_token

    tok = issue_stepup_token(user_id=1, app="pazuru")
    assert _refresh(client, tok, internal=False).status_code == 403


def test_refresh_rejected_when_internal_token_unconfigured(client, monkeypatch):
    from config import settings
    from stepup import issue_stepup_token

    monkeypatch.setattr(settings, "internal_api_token", "")
    tok = issue_stepup_token(user_id=1, app="pazuru")
    assert _refresh(client, tok).status_code == 403


def test_refresh_refuses_past_absolute_cap(client, internal_token):
    import time

    from stepup import issue_stepup_token

    old = int(time.time()) - 13 * 3600
    tok = issue_stepup_token(user_id=1, app="pazuru", auth_time=old)
    assert _refresh(client, tok).status_code == 401


def test_refresh_keeps_original_auth_time(client, internal_token):
    import time

    import jwt as pyjwt

    from stepup import issue_stepup_token

    at = int(time.time()) - 3600
    resp = _refresh(client, issue_stepup_token(user_id=1, app="pazuru", auth_time=at))
    assert resp.status_code == 200
    claims = pyjwt.decode(resp.json()["token"], options={"verify_signature": False})
    assert claims["auth_time"] == at
    assert claims["typ"] == "stepup"


def test_refresh_refuses_after_session_floor_raised(client, internal_token):
    from stepup import issue_stepup_token

    tok = issue_stepup_token(user_id=1, app="pazuru", session_version=1)
    conn = client.app.dependency_overrides[get_conn]()
    conn.execute("UPDATE users SET session_version = 2 WHERE id = 1")
    conn.commit()
    assert _refresh(client, tok).status_code == 401
