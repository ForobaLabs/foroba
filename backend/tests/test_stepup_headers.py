"""T8: Foroba step-up /verify returns token in body for X-Client: native."""

from __future__ import annotations

import sqlite3

import pyotp
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


@pytest.fixture
def authed_client_with_totp(client):
    """Register a user, enroll TOTP, return (client, totp_secret)."""
    client.post(
        "/auth/register",
        json={
            "email": "native@example.com",
            "email_confirm": "native@example.com",
            "name": "Native",
            "password": "Nat1vePass!x",
            "password_confirm": "Nat1vePass!x",
            "tos_accepted": True,
        },
    )
    enroll = client.post("/auth/2fa/enroll")
    secret = enroll.json()["secret"]
    code = pyotp.TOTP(secret).now()
    client.post("/auth/2fa/verify", json={"code": code})
    return client, secret


def _stepup_payload(secret: str, app_name: str = "pazuru") -> dict:
    code = pyotp.TOTP(secret).now()
    return {"app": app_name, "method": "totp", "code": code}


def test_native_client_receives_the_stepup_token_in_the_body(authed_client_with_totp):
    client, secret = authed_client_with_totp
    payload = _stepup_payload(secret)
    resp = client.post(
        "/auth/stepup/verify",
        json=payload,
        headers={"X-Client": "native"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["app"] == payload["app"]
    assert body["token"].count(".") == 2  # a JWT (header.payload.sig)


def test_web_client_response_body_does_not_contain_token(authed_client_with_totp):
    client, secret = authed_client_with_totp
    resp = client.post("/auth/stepup/verify", json=_stepup_payload(secret))
    assert resp.status_code == 200
    assert "token" not in resp.json()


def test_web_client_still_gets_the_cookie(authed_client_with_totp):
    client, secret = authed_client_with_totp
    payload = _stepup_payload(secret, app_name="tsumi")
    resp = client.post("/auth/stepup/verify", json=payload)
    assert resp.status_code == 200
    assert "stepup_tsumi" in resp.cookies
