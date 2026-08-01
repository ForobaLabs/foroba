import json
import sqlite3

from fastapi.testclient import TestClient

from auth.conn import get_conn
from auth.dependencies import get_current_user
from db import init_schema
from main import app
from settings_store import init_settings, set_value


async def _fake_gather_dataframes(*a, **k):
    return {}


async def _fake_run_lab_turn(**kwargs):
    yield {"type": "token", "value": "hello"}
    yield {"type": "done", "code": "result_text = 'hi'", "context": "ctx"}


def test_lab_chat_streams_ndjson(monkeypatch):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    init_settings(conn)

    import lab_router

    monkeypatch.setattr(lab_router, "gather_dataframes", _fake_gather_dataframes)
    monkeypatch.setattr(lab_router, "run_lab_turn", _fake_run_lab_turn)

    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "u1@test.local"}

    try:
        client = TestClient(app)
        response = client.post("/lab/chat", json={"message": "hi", "session_id": "s1"})

        assert response.status_code == 200
        lines = [json.loads(line) for line in response.text.strip().splitlines()]
        assert lines[0]["type"] == "token"
        assert lines[-1]["type"] == "done"
    finally:
        app.dependency_overrides.clear()


def test_lab_chat_hard_disabled_in_hosted_deployment_mode(monkeypatch):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    init_settings(conn)

    import lab_router

    monkeypatch.setattr(lab_router.settings, "deployment_mode", "hosted")
    monkeypatch.setattr(lab_router, "gather_dataframes", _fake_gather_dataframes)
    monkeypatch.setattr(lab_router, "run_lab_turn", _fake_run_lab_turn)

    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "u1@test.local"}

    try:
        client = TestClient(app)
        response = client.post("/lab/chat", json={"message": "hi", "session_id": "s1"})

        assert response.status_code == 200
        lines = [json.loads(line) for line in response.text.strip().splitlines()]
        assert len(lines) == 1
        assert lines[0]["type"] == "error"
        assert "hosted beta" in lines[0]["value"].lower()
    finally:
        app.dependency_overrides.clear()


def test_lab_chat_disabled_returns_graceful_message(monkeypatch):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    init_settings(conn)
    set_value(conn, "lab_service_enabled", "false")

    import lab_router

    monkeypatch.setattr(lab_router, "gather_dataframes", _fake_gather_dataframes)
    monkeypatch.setattr(lab_router, "run_lab_turn", _fake_run_lab_turn)

    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "u1@test.local"}

    try:
        client = TestClient(app)
        response = client.post("/lab/chat", json={"message": "hi", "session_id": "s1"})

        assert response.status_code == 200
        lines = [json.loads(line) for line in response.text.strip().splitlines()]
        assert len(lines) == 1
        assert lines[0]["type"] == "error"
        assert "unavailable" in lines[0]["value"].lower()
    finally:
        app.dependency_overrides.clear()
