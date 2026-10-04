"""AI-6-F4: Foroba exposes the persisted session-version floors so Pazuru/Tsumi can
re-sync after a restart (their in-memory floor is otherwise lost)."""

from __future__ import annotations

import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import repository as repo
from auth.conn import get_conn
from config import settings
from db import init_schema, seed_mock_users
from session_floors_router import router


def _client(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_token", "right-token")
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    seed_mock_users(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(router)
    return TestClient(app), conn


def test_requires_internal_token(monkeypatch):
    c, _ = _client(monkeypatch)
    assert c.get("/internal/session-floors").status_code == 403
    bad = {"X-Internal-Token": "bad"}
    assert c.get("/internal/session-floors", headers=bad).status_code == 403


def test_returns_only_bumped_floors(monkeypatch):
    c, conn = _client(monkeypatch)
    uid = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()["id"]
    h = {"X-Internal-Token": "right-token"}
    assert c.get("/internal/session-floors", headers=h).json() == {"floors": {}}
    new = repo.bump_session_version(conn, uid)
    body = c.get("/internal/session-floors", headers=h).json()
    assert body == {"floors": {str(uid): new}}
