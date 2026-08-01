import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import repository as repo
from auth.dependencies import get_current_user
from auth.router import get_conn, router
from auth.security import hash_password
from db import init_schema


@pytest.fixture
def client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(router)
    return TestClient(app)


def test_register_then_me(client):
    r = client.post(
        "/auth/register",
        json={
            "email": "x@y.com",
            "email_confirm": "x@y.com",
            "name": "X",
            "password": "password123",
            "password_confirm": "password123",
        },
    )
    assert r.status_code == 201, r.text
    assert client.cookies.get("suite_session")

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "x@y.com"


def test_login_wrong_password_401(client):
    client.post("/auth/register", json={"email": "x@y.com", "name": "X", "password": "password123"})
    r = client.post("/auth/login", json={"email": "x@y.com", "password": "nope"})
    assert r.status_code == 401


def test_me_without_cookie_401(client):
    assert client.get("/auth/me").status_code == 401


def test_update_display_currency(client):
    register = client.post(
        "/auth/register",
        json={
            "email": "curr@y.com",
            "email_confirm": "curr@y.com",
            "name": "Curr User",
            "password": "password123",
            "password_confirm": "password123",
        },
    )
    assert register.status_code == 201

    resp = client.put("/auth/me/currency", json={"display_currency": "USD"})
    assert resp.status_code == 204

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["display_currency"] == "USD"


def test_put_show_debts_updates_preference():
    # Builds its own conn/app (rather than reusing the shared `client` fixture) and
    # overrides get_current_user directly, so it never calls /auth/register or
    # /auth/login — both rate-limited endpoints whose buckets are shared process-wide
    # across every test file in the same pytest session.
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    user = repo.create_user(
        conn,
        email="debts-toggle@y.com",
        name="Debts Toggle",
        password_hash=hash_password("password123"),
    )
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: repo.get_user_by_id(conn, user["id"])
    app.include_router(router)
    local_client = TestClient(app)

    resp = local_client.put("/auth/me/show-debts", json={"show_debts": True})
    assert resp.status_code == 204


def test_update_name_splits_and_returns_in_me():
    # Same pattern as test_put_show_debts_updates_preference — avoids the
    # rate-limited /auth/register endpoint by creating the user directly.
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    user = repo.create_user(
        conn,
        email="rename-router@y.com",
        name="Old Name",
        password_hash=hash_password("password123"),
    )
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: repo.get_user_by_id(conn, user["id"])
    app.include_router(router)
    local_client = TestClient(app)

    resp = local_client.put("/auth/me/name", json={"first_name": "New", "last_name": "Name"})
    assert resp.status_code == 204

    app.dependency_overrides[get_current_user] = lambda: repo.get_user_by_id(conn, user["id"])
    me = local_client.get("/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["first_name"] == "New"
    assert body["last_name"] == "Name"
    assert body["name"] == "New Name"
