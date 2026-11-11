"""Tests for change-password and forgot-password endpoints (foroba#256)."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.conn import get_conn
from auth.router import router as auth_router
from auth.token_router import router as token_router
from db import init_schema
from rate_limit import limiter
from settings_store import init_settings

_EMAIL = "pwchange@example.com"
_PASSWORD = "OldPass1!long"
_NEW_PASSWORD = "NewPass2@long"


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    init_settings(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(auth_router)
    app.include_router(token_router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def registered(client):
    r = client.post(
        "/auth/register",
        json={
            "email": _EMAIL,
            "email_confirm": _EMAIL,
            "name": "PwChange",
            "password": _PASSWORD,
            "password_confirm": _PASSWORD,
            "tos_accepted": True,
        },
    )
    assert r.status_code == 201
    return client


def _login_cookie(client) -> dict:
    r = client.post(
        "/auth/login",
        json={"email": _EMAIL, "password": _PASSWORD},
    )
    assert r.status_code == 200
    return {}  # cookie is set automatically by TestClient


def _bearer(client, password: str = _PASSWORD) -> str:
    r = client.post(
        "/auth/token",
        json={"email": _EMAIL, "password": password, "device_label": "test-device"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


# ── change password (PUT /auth/me/password) ───────────────────────────────────

def test_change_password_succeeds(registered):
    token = _bearer(registered)
    r = registered.put(
        "/auth/me/password",
        json={
            "current_password": _PASSWORD,
            "new_password": _NEW_PASSWORD,
            "new_password_confirm": _NEW_PASSWORD,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204


def test_change_password_wrong_current(registered):
    token = _bearer(registered)
    r = registered.put(
        "/auth/me/password",
        json={
            "current_password": "WrongPass1!",
            "new_password": _NEW_PASSWORD,
            "new_password_confirm": _NEW_PASSWORD,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401


def test_change_password_confirm_mismatch(registered):
    token = _bearer(registered)
    r = registered.put(
        "/auth/me/password",
        json={
            "current_password": _PASSWORD,
            "new_password": _NEW_PASSWORD,
            "new_password_confirm": "Different3#x",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


def test_change_password_revokes_refresh_tokens(registered):
    """After changing password, an existing refresh token must be rejected."""
    pair = registered.post(
        "/auth/token",
        json={"email": _EMAIL, "password": _PASSWORD, "device_label": "old-device"},
    ).json()
    old_refresh = pair["refresh_token"]
    access = pair["access_token"]

    registered.put(
        "/auth/me/password",
        json={
            "current_password": _PASSWORD,
            "new_password": _NEW_PASSWORD,
            "new_password_confirm": _NEW_PASSWORD,
        },
        headers={"Authorization": f"Bearer {access}"},
    )

    replay = registered.post(
        "/auth/token/refresh", json={"refresh_token": old_refresh}
    )
    assert replay.status_code == 401


def test_change_password_new_password_works(registered):
    """After a successful change, old password must stop working and new one must work."""
    token = _bearer(registered)
    registered.put(
        "/auth/me/password",
        json={
            "current_password": _PASSWORD,
            "new_password": _NEW_PASSWORD,
            "new_password_confirm": _NEW_PASSWORD,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    old_login = registered.post(
        "/auth/login", json={"email": _EMAIL, "password": _PASSWORD}
    )
    assert old_login.status_code == 401

    new_login = registered.post(
        "/auth/login", json={"email": _EMAIL, "password": _NEW_PASSWORD}
    )
    assert new_login.status_code == 200


def test_change_password_requires_auth(client):
    """No auth header, no cookie → 401."""
    r = client.put(
        "/auth/me/password",
        json={
            "current_password": _PASSWORD,
            "new_password": _NEW_PASSWORD,
            "new_password_confirm": _NEW_PASSWORD,
        },
    )
    assert r.status_code == 401


# ── reset request (POST /auth/me/password/reset-request) ─────────────────────

def test_reset_request_unknown_email_returns_204(registered):
    """No oracle — always 204 even for unknown emails."""
    r = registered.post(
        "/auth/me/password/reset-request",
        json={"email": "nobody@example.com"},
    )
    assert r.status_code == 204


def test_reset_request_known_email_without_smtp_returns_204(registered, monkeypatch):
    """Without SMTP configured the endpoint still returns 204 (no account oracle)."""
    import config as cfg
    monkeypatch.setattr(cfg.settings, "smtp_enabled", False)
    r = registered.post(
        "/auth/me/password/reset-request",
        json={"email": _EMAIL},
    )
    assert r.status_code == 204


# ── reset confirm (POST /auth/me/password/reset) ──────────────────────────────

def test_reset_confirm_bad_code_returns_400(registered):
    r = registered.post(
        "/auth/me/password/reset",
        json={
            "email": _EMAIL,
            "code": "000000",
            "new_password": _NEW_PASSWORD,
            "new_password_confirm": _NEW_PASSWORD,
        },
    )
    assert r.status_code == 400


def test_reset_confirm_unknown_email_returns_400(registered):
    r = registered.post(
        "/auth/me/password/reset",
        json={
            "email": "nobody@example.com",
            "code": "000000",
            "new_password": _NEW_PASSWORD,
            "new_password_confirm": _NEW_PASSWORD,
        },
    )
    assert r.status_code == 400
