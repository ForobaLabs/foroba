"""Route tests for GET /notifications + POST /notifications/{key}/dismiss (foroba#158)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import db as db_module
from auth.conn import get_conn
from auth.dependencies import get_current_user
from main import app


def _memory_conn():
    return db_module.connect(":memory:")


async def _fake_generate_notifications(conn, user_id, *, cookie=None, **_):
    return {
        "items": [
            {
                "key": "goal_reached:1",
                "type": "goal_reached",
                "severity": "positive",
                "title": "Goal reached",
                "message": "You reached your goal",
            }
        ],
        "degraded": False,
    }


def test_notifications_route_requires_auth():
    client = TestClient(app)
    resp = client.get("/notifications")
    assert resp.status_code in (401, 403)


def test_notifications_route_returns_items(monkeypatch):
    import notification_service as ns

    monkeypatch.setattr(ns, "generate_notifications", _fake_generate_notifications)
    conn = _memory_conn()
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "u1@test.local"}
    app.dependency_overrides[get_conn] = lambda: conn
    try:
        client = TestClient(app)
        resp = client.get("/notifications")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["key"] == "goal_reached:1"
        assert body["degraded"] is False
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_conn, None)


def test_dismiss_notification_persists(monkeypatch):
    conn = _memory_conn()
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "u1@test.local"}
    app.dependency_overrides[get_conn] = lambda: conn
    try:
        client = TestClient(app)
        resp = client.post("/notifications/goal_reached:1/dismiss")
        assert resp.status_code == 200
        assert resp.json()["dismissed"] is True
        assert "goal_reached:1" in db_module.get_dismissed_notification_keys(conn, 1)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_conn, None)
