"""AI-6-F14: unknown-account logins must cost one password verification, like known ones."""

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import security
from auth.conn import get_conn
from auth.router import router as auth_router
from auth.token_router import router as token_router
from db import init_schema, seed_mock_users
from rate_limit import limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    seed_mock_users(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(auth_router)
    app.include_router(token_router)
    return TestClient(app)


@pytest.mark.parametrize("path", ["/auth/login", "/auth/token"])
@pytest.mark.parametrize("email", ["nobody-here@example.com", "demo@foroba.app"])
def test_failed_login_verifies_exactly_once(client, monkeypatch, path, email):
    calls: list[str] = []
    real = security.verify_password

    def counting(plain, hashed):
        calls.append(hashed)
        return real(plain, hashed)

    monkeypatch.setattr(security, "verify_password", counting)
    r = client.post(
        path, json={"email": email, "password": "definitely-wrong-pw", "device_label": "test"}
    )
    assert r.status_code == 401
    assert len(calls) == 1


def test_unknown_account_is_verified_against_the_dummy_hash(client, monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(security, "verify_password", lambda p, h: seen.append(h) or False)
    client.post("/auth/login", json={"email": "ghost@example.com", "password": "x" * 12})
    assert seen == [security._DUMMY_HASH]
