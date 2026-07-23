"""Route tests for /auth/webhooks CRUD (foroba#165, TI-D item 5, Plan A)."""
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


def test_create_requires_https():
    conn = _memory_conn()
    app.dependency_overrides[get_current_user] = lambda: _USER
    app.dependency_overrides[get_conn] = lambda: conn
    try:
        client = TestClient(app)
        resp = client.post("/auth/webhooks", json={"target_url": "http://example.com/hook"})
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_conn, None)


def test_create_list_delete_reactivate_roundtrip():
    conn = _memory_conn()
    app.dependency_overrides[get_current_user] = lambda: _USER
    app.dependency_overrides[get_conn] = lambda: conn
    try:
        client = TestClient(app)
        created = client.post("/auth/webhooks", json={"target_url": "https://example.com/hook"})
        assert created.status_code == 201
        body = created.json()
        assert body["target_url"] == "https://example.com/hook"
        assert len(body["signing_secret"]) > 20
        webhook_id = body["id"]

        listed = client.get("/auth/webhooks")
        assert listed.status_code == 200
        assert "signing_secret" not in listed.json()[0]

        db.register_webhook_failure(conn, webhook_id)
        reactivated = client.post(f"/auth/webhooks/{webhook_id}/reactivate")
        assert reactivated.status_code == 200
        assert reactivated.json()["consecutive_failures"] == 0

        deleted = client.delete(f"/auth/webhooks/{webhook_id}")
        assert deleted.status_code == 204
        assert client.get("/auth/webhooks").json() == []
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_conn, None)


def test_reactivate_unknown_webhook_is_404():
    conn = _memory_conn()
    app.dependency_overrides[get_current_user] = lambda: _USER
    app.dependency_overrides[get_conn] = lambda: conn
    try:
        client = TestClient(app)
        resp = client.post("/auth/webhooks/999/reactivate")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_conn, None)
