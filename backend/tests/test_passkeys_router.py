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
