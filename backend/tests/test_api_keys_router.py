"""Route tests for /auth/api-keys CRUD (foroba#165, TI-D item 5, Plan A)."""
from __future__ import annotations

from fastapi.testclient import TestClient

import db
from auth.conn import get_conn
from auth.dependencies import get_current_user
from main import app

_USER = {"id": 1, "email": "u@test.local", "tier": "premium", "audience": "base",
         "is_admin": 0, "household_id": None}


def _memory_conn():
    return db.connect(":memory:")


def test_create_list_revoke_api_key_roundtrip():
    conn = _memory_conn()
    app.dependency_overrides[get_current_user] = lambda: _USER
    app.dependency_overrides[get_conn] = lambda: conn
    try:
        client = TestClient(app)
        created = client.post("/auth/api-keys", json={"label": "n8n workflow"})
        assert created.status_code == 201
        body = created.json()
        assert body["label"] == "n8n workflow"
        assert "." in body["key"]
        key_id = body["id"]

        listed = client.get("/auth/api-keys")
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        assert "key" not in listed.json()[0]
        assert "secret_hash" not in listed.json()[0]

        revoked = client.delete(f"/auth/api-keys/{key_id}")
        assert revoked.status_code == 204

        listed_again = client.get("/auth/api-keys")
        assert listed_again.json()[0]["is_active"] is False
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_conn, None)


def test_revoke_unknown_key_is_404():
    conn = _memory_conn()
    app.dependency_overrides[get_current_user] = lambda: _USER
    app.dependency_overrides[get_conn] = lambda: conn
    try:
        client = TestClient(app)
        resp = client.delete("/auth/api-keys/999")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_conn, None)
