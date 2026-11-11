"""Pre-beta Task 2.2: password change/reset revoke every session; 12-char minimum;
reset-request gives no account oracle."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import config
from auth import repository as repo
from auth.conn import get_conn
from auth.router import router as auth_router
from auth.token_router import router as token_router
from db import init_schema
from rate_limit import limiter
from settings_store import init_settings

_EMAIL = "hardening@example.com"
_PASSWORD = "Old-Passw0rd!x"
_NEW = "New-Passw0rd!y"


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def ctx(monkeypatch):
    pushed: list[tuple[int, int]] = []
    monkeypatch.setattr(
        "auth.router.invalidate_sessions_downstream",
        lambda uid, version: pushed.append((uid, version)),
    )
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    init_settings(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(auth_router)
    app.include_router(token_router)
    c = TestClient(app, raise_server_exceptions=False)
    r = c.post("/auth/register", json=_register_body(_PASSWORD))
    assert r.status_code == 201, r.text
    c.cookies.clear()
    return c, conn, pushed


def _register_body(password: str, email: str = _EMAIL) -> dict:
    return {
        "email": email,
        "email_confirm": email,
        "name": "Hardening",
        "password": password,
        "password_confirm": password,
        "tos_accepted": True,
    }


def _access(c: TestClient, password: str = _PASSWORD) -> str:
    r = c.post(
        "/auth/token", json={"email": _EMAIL, "password": password, "device_label": "d"}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _me(c: TestClient, token: str) -> int:
    return c.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code


def test_change_password_revokes_other_sessions_and_pushes_downstream(ctx):
    c, conn, pushed = ctx
    other_device = _access(c)
    this_device = _access(c)
    r = c.put(
        "/auth/me/password",
        json={"current_password": _PASSWORD, "new_password": _NEW, "new_password_confirm": _NEW},
        headers={"Authorization": f"Bearer {this_device}"},
    )
    assert r.status_code == 204
    assert _me(c, other_device) == 401
    user = repo.get_user_by_email(conn, _EMAIL)
    assert pushed == [(user["id"], user["session_version"])]


def test_change_password_keeps_the_current_cookie_session(ctx):
    c, _, _ = ctx
    assert c.post("/auth/login", json={"email": _EMAIL, "password": _PASSWORD}).status_code == 200
    r = c.put(
        "/auth/me/password",
        json={"current_password": _PASSWORD, "new_password": _NEW, "new_password_confirm": _NEW},
    )
    assert r.status_code == 204
    assert c.get("/auth/me").status_code == 200


def test_password_reset_revokes_every_session(ctx, monkeypatch):
    c, conn, pushed = ctx
    token = _access(c)
    monkeypatch.setattr("auth.router.verify_email_otp", lambda conn, uid, code: True)
    r = c.post(
        "/auth/me/password/reset",
        json={
            "email": _EMAIL,
            "code": "123456",
            "new_password": _NEW,
            "new_password_confirm": _NEW,
        },
    )
    assert r.status_code == 204
    assert _me(c, token) == 401
    user = repo.get_user_by_email(conn, _EMAIL)
    assert pushed == [(user["id"], user["session_version"])]


def test_reset_request_known_email_without_smtp_gives_no_oracle(ctx, monkeypatch):
    c, _, _ = ctx
    monkeypatch.setattr(config.settings, "smtp_enabled", False)
    known = c.post("/auth/me/password/reset-request", json={"email": _EMAIL})
    unknown = c.post("/auth/me/password/reset-request", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 204


@pytest.mark.parametrize("password", ["Short1!", "Elevenchar!"])
def test_register_rejects_passwords_under_12_chars(ctx, password):
    c, _, _ = ctx
    r = c.post("/auth/register", json=_register_body(password, "short@example.com"))
    assert r.status_code == 422


def test_change_password_rejects_under_12_chars(ctx):
    c, _, _ = ctx
    r = c.put(
        "/auth/me/password",
        json={
            "current_password": _PASSWORD,
            "new_password": "Elevenchar!",
            "new_password_confirm": "Elevenchar!",
        },
        headers={"Authorization": f"Bearer {_access(c)}"},
    )
    assert r.status_code == 422


def test_reset_rejects_under_12_chars(ctx):
    c, _, _ = ctx
    r = c.post(
        "/auth/me/password/reset",
        json={
            "email": _EMAIL,
            "code": "123456",
            "new_password": "Elevenchar!",
            "new_password_confirm": "Elevenchar!",
        },
    )
    assert r.status_code == 422
