"""XAPP-D03: logout must invalidate the already-issued suite_session JWT
immediately, not just clear the local cookie and revoke future refresh
tokens. Mirrors test_login_2fa_flow.py's _client() fixture pattern."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import repository as repo
from auth.conn import get_conn
from auth.router import router as auth_router
from db import init_schema, seed_mock_users
from rate_limit import limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


def _client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    seed_mock_users(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(auth_router)
    return TestClient(app), conn


def test_logout_invalidates_suite_session_immediately(monkeypatch):
    c, _conn = _client()
    # Downstream push is best-effort and unreachable in this unit test (no
    # real Pazuru/Tsumi process) -- patch it out so logout doesn't spend
    # time on doomed httpx calls / log noise, without changing behavior
    # under test (the local session_version bump + /auth/me check).
    monkeypatch.setattr(
        "auth.router.invalidate_sessions_downstream", lambda *a, **k: None
    )

    login_r = c.post("/auth/login", json={"email": "demo@foroba.app", "password": "Demo!2026"})
    assert login_r.status_code == 200
    old_session_cookie = c.cookies.get("suite_session")
    assert old_session_cookie

    # Sanity: the cookie is valid before logout.
    me_before = c.get("/auth/me")
    assert me_before.status_code == 200

    logout_r = c.post("/auth/logout")
    assert logout_r.status_code == 204

    # Replay the old cookie value directly against a protected endpoint --
    # this must now be rejected even though the JWT's own `exp` claim has
    # not expired yet.
    c.cookies.set("suite_session", old_session_cookie)
    me_after = c.get("/auth/me")
    assert me_after.status_code == 401


def test_session_version_bumps_on_each_logout(monkeypatch):
    c, conn = _client()
    monkeypatch.setattr(
        "auth.router.invalidate_sessions_downstream", lambda *a, **k: None
    )
    demo = repo.get_user_by_email(conn, "demo@foroba.app")
    assert repo.get_session_version(conn, demo["id"]) == 1

    c.post("/auth/login", json={"email": "demo@foroba.app", "password": "Demo!2026"})
    c.post("/auth/logout")
    assert repo.get_session_version(conn, demo["id"]) == 2

    c.post("/auth/login", json={"email": "demo@foroba.app", "password": "Demo!2026"})
    c.post("/auth/logout")
    assert repo.get_session_version(conn, demo["id"]) == 3
