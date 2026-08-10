"""Cookieless token endpoints for native clients (T9+T10)."""

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

_USER_EMAIL = "native@example.com"
_USER_PASSWORD = "Nat1vePass!"
_OTHER_EMAIL = "other@example.com"
_OTHER_PASSWORD = "Other1Pass!"


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
def seeded_user(client):
    client.post(
        "/auth/register",
        json={
            "email": _USER_EMAIL,
            "email_confirm": _USER_EMAIL,
            "name": "Native",
            "password": _USER_PASSWORD,
            "password_confirm": _USER_PASSWORD,
            "tos_accepted": True,
        },
    )
    return {"email": _USER_EMAIL, "password": _USER_PASSWORD}


@pytest.fixture
def other_user(client):
    client.post(
        "/auth/register",
        json={
            "email": _OTHER_EMAIL,
            "email_confirm": _OTHER_EMAIL,
            "name": "Other",
            "password": _OTHER_PASSWORD,
            "password_confirm": _OTHER_PASSWORD,
            "tos_accepted": True,
        },
    )
    return {"email": _OTHER_EMAIL, "password": _OTHER_PASSWORD}


def _issue(client, user, label: str = "iPhone 15") -> dict:
    r = client.post(
        "/auth/token",
        json={"email": user["email"], "password": user["password"], "device_label": label},
    )
    assert r.status_code == 200, r.text
    return r.json()


# ── T9 tests ──────────────────────────────────────────────────────────────────

def test_token_returns_access_and_refresh(client, seeded_user):
    body = _issue(client, seeded_user)
    assert body["token_type"] == "Bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in"] == 15 * 60
    assert body["user"]["email"] == seeded_user["email"]


def test_token_sets_no_cookie(client, seeded_user):
    r = client.post(
        "/auth/token",
        json={
            "email": seeded_user["email"],
            "password": seeded_user["password"],
            "device_label": "iPhone 15",
        },
    )
    assert "set-cookie" not in {k.lower() for k in r.headers}


def test_token_access_token_works_as_bearer(client, seeded_user):
    token = _issue(client, seeded_user)["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_token_rejects_bad_password(client, seeded_user):
    r = client.post(
        "/auth/token",
        json={
            "email": seeded_user["email"],
            "password": "wrong-password",
            "device_label": "iPhone 15",
        },
    )
    assert r.status_code == 401


def test_token_requires_device_label(client, seeded_user):
    r = client.post(
        "/auth/token",
        json={"email": seeded_user["email"], "password": seeded_user["password"]},
    )
    assert r.status_code == 422


def test_refresh_rotates_and_returns_new_pair(client, seeded_user):
    first = _issue(client, seeded_user)
    r = client.post("/auth/token/refresh", json={"refresh_token": first["refresh_token"]})
    assert r.status_code == 200
    second = r.json()
    assert second["access_token"]
    assert second["refresh_token"] != first["refresh_token"]


def test_refresh_reuse_is_rejected(client, seeded_user):
    first = _issue(client, seeded_user)
    client.post("/auth/token/refresh", json={"refresh_token": first["refresh_token"]})
    replay = client.post("/auth/token/refresh", json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401


def test_revoke_invalidates_refresh_token(client, seeded_user):
    pair = _issue(client, seeded_user)
    assert client.post(
        "/auth/token/revoke", json={"refresh_token": pair["refresh_token"]}
    ).status_code == 204
    r = client.post("/auth/token/refresh", json={"refresh_token": pair["refresh_token"]})
    assert r.status_code == 401


# ── T10 tests — session management ───────────────────────────────────────────

def test_sessions_lists_only_own_devices(client, seeded_user, other_user):
    mine = _issue(client, seeded_user)
    _issue(client, other_user, label="Someone else's Pixel")
    r = client.get(
        "/auth/sessions", headers={"Authorization": f"Bearer {mine['access_token']}"}
    )
    assert r.status_code == 200
    labels = [s["device_label"] for s in r.json()["sessions"]]
    assert labels == ["iPhone 15"]


def test_sessions_never_return_the_token(client, seeded_user):
    pair = _issue(client, seeded_user)
    r = client.get(
        "/auth/sessions", headers={"Authorization": f"Bearer {pair['access_token']}"}
    )
    serialized = r.text
    assert pair["refresh_token"] not in serialized
    assert "token_hash" not in serialized


def test_delete_session_kills_that_refresh_token(client, seeded_user):
    pair = _issue(client, seeded_user)
    headers = {"Authorization": f"Bearer {pair['access_token']}"}
    session_id = client.get("/auth/sessions", headers=headers).json()["sessions"][0]["id"]
    assert client.delete(f"/auth/sessions/{session_id}", headers=headers).status_code == 204
    assert (
        client.post(
            "/auth/token/refresh", json={"refresh_token": pair["refresh_token"]}
        ).status_code
        == 401
    )


def test_cannot_delete_another_users_session(client, seeded_user, other_user):
    victim = _issue(client, other_user, label="Victim phone")
    attacker = _issue(client, seeded_user, label="Attacker phone")
    victim_headers = {"Authorization": f"Bearer {victim['access_token']}"}
    victim_session = client.get("/auth/sessions", headers=victim_headers).json()["sessions"][0]
    r = client.delete(
        f"/auth/sessions/{victim_session['id']}",
        headers={"Authorization": f"Bearer {attacker['access_token']}"},
    )
    assert r.status_code == 404
    # Victim's token must still work
    assert (
        client.post(
            "/auth/token/refresh", json={"refresh_token": victim["refresh_token"]}
        ).status_code
        == 200
    )
