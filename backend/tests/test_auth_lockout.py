import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import repository as repo
from auth.router import get_conn, router
from db import init_schema
from rate_limit import limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # /auth/login is rate-limited (10/minute), shared across the whole test session
    # since `limiter` is a module-level singleton — reset between tests so this file's
    # repeated login attempts don't bleed into other test files.
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(router)
    return TestClient(app), conn


def test_lockout_after_five_failed_attempts(client):
    c, _conn = client
    c.post("/auth/register", json={
        "email": "lock@y.com", "email_confirm": "lock@y.com", "name": "L",
        "password": "password123", "password_confirm": "password123"})
    c.cookies.clear()

    for _ in range(repo.LOCKOUT_MAX_ATTEMPTS):
        r = c.post("/auth/login", json={"email": "lock@y.com", "password": "wrong"})
        assert r.status_code == 401

    r = c.post("/auth/login", json={"email": "lock@y.com", "password": "password123"})
    assert r.status_code == 423


def test_successful_login_resets_counter(client):
    c, conn = client
    c.post("/auth/register", json={
        "email": "reset@y.com", "email_confirm": "reset@y.com", "name": "R",
        "password": "password123", "password_confirm": "password123"})
    c.cookies.clear()

    c.post("/auth/login", json={"email": "reset@y.com", "password": "wrong"})
    c.post("/auth/login", json={"email": "reset@y.com", "password": "wrong"})
    r = c.post("/auth/login", json={"email": "reset@y.com", "password": "password123"})
    assert r.status_code == 200

    user = repo.get_user_by_email(conn, "reset@y.com")
    assert user["failed_login_attempts"] == 0
    assert user["locked_until"] is None


def test_disabled_account_cannot_login(client):
    c, conn = client
    c.post("/auth/register", json={
        "email": "disabled@y.com", "email_confirm": "disabled@y.com", "name": "D",
        "password": "password123", "password_confirm": "password123"})
    c.cookies.clear()

    user = repo.get_user_by_email(conn, "disabled@y.com")
    repo.set_account_disabled(conn, user["id"], True)

    r = c.post("/auth/login", json={"email": "disabled@y.com", "password": "password123"})
    assert r.status_code == 403

    repo.set_account_disabled(conn, user["id"], False)
    r2 = c.post("/auth/login", json={"email": "disabled@y.com", "password": "password123"})
    assert r2.status_code == 200
