import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.conn import get_conn
from db import init_schema
from passkeys.router import router


@pytest.fixture
def client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(router)
    return TestClient(app)


def test_registration_options_requires_auth(client):
    resp = client.post("/auth/webauthn/register/options")
    assert resp.status_code == 401


def test_registration_options_returns_challenge(client, monkeypatch):
    monkeypatch.setenv("AUTH_DEV_BYPASS", "true")
    resp = client.post("/auth/webauthn/register/options")
    assert resp.status_code == 200
    assert "challenge" in resp.json()
    monkeypatch.delenv("AUTH_DEV_BYPASS", raising=False)


def test_authenticate_options_requires_auth(client):
    resp = client.post("/auth/webauthn/authenticate/options")
    assert resp.status_code == 401


def test_authenticate_options_returns_challenge_for_enrolled_user(client, monkeypatch):
    monkeypatch.setenv("AUTH_DEV_BYPASS", "true")
    resp = client.post("/auth/webauthn/authenticate/options")
    assert resp.status_code == 200
    assert "challenge" in resp.json()
    monkeypatch.delenv("AUTH_DEV_BYPASS", raising=False)


# --- Task 2b: credentials registered under a previous RP ID ---


@pytest.fixture
def full_client(monkeypatch):
    from auth.router import router as auth_router
    from config import settings
    from rate_limit import limiter
    from settings_store import init_settings
    from twofa.router import router as twofa_router

    limiter.reset()
    monkeypatch.setattr(settings, "webauthn_rp_id", "forobalabs.com")
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    init_settings(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(auth_router)
    app.include_router(twofa_router)
    app.include_router(router)
    c = TestClient(app)
    resp = c.post(
        "/auth/register",
        json={
            "email": "pk@example.com",
            "email_confirm": "pk@example.com",
            "name": "Pk User",
            "password": "Sup3rSecret!",
            "password_confirm": "Sup3rSecret!",
            "tos_accepted": True,
        },
    )
    assert resp.status_code in (200, 201), resp.text
    c.conn = conn
    c.user_id = resp.json()["id"]
    yield c
    limiter.reset()


def _give_passkey(c, raw_id: str, rp_id: str | None) -> None:
    c.conn.execute(
        "INSERT INTO webauthn_credentials "
        "(user_id, credential_id, public_key, sign_count, label, rp_id) "
        "VALUES (?, ?, 'pk', 0, 'k', ?)",
        (c.user_id, raw_id, rp_id),
    )
    c.conn.execute("UPDATE users SET webauthn_enabled = 1 WHERE id = ?", (c.user_id,))
    c.conn.commit()


def test_me_passkey_reenrol_needed(full_client):
    c = full_client
    assert c.get("/auth/me").json()["passkey_reenrol_needed"] is False  # no credentials
    _give_passkey(c, "b2xk", "foroba-app.duckdns.org")
    assert c.get("/auth/me").json()["passkey_reenrol_needed"] is True  # stale only
    _give_passkey(c, "bmV3", "forobalabs.com")
    assert c.get("/auth/me").json()["passkey_reenrol_needed"] is False  # one current


def test_stepup_methods_hide_passkey_when_only_stale(full_client):
    c = full_client
    _give_passkey(c, "b2xk", "foroba-app.duckdns.org")
    assert c.get("/auth/2fa/methods").json()["webauthn_enabled"] is False
    _give_passkey(c, "bmV3", "forobalabs.com")
    assert c.get("/auth/2fa/methods").json()["webauthn_enabled"] is True


def test_login_options_refused_when_only_stale(full_client):
    c = full_client
    _give_passkey(c, "b2xk", "foroba-app.duckdns.org")
    resp = c.post("/auth/login/webauthn/options-by-email", json={"email": "pk@example.com"})
    assert resp.status_code == 400
    _give_passkey(c, "bmV3", "forobalabs.com")
    resp = c.post("/auth/login/webauthn/options-by-email", json={"email": "pk@example.com"})
    assert resp.status_code == 200
