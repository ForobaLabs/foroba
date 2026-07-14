import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import init_schema
from auth.router import router, get_conn
from auth import repository as repo


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
    c, conn = client
    c.post("/auth/register", json={
        "email": "lock@y.com", "name": "L", "password": "password123"})
    c.cookies.clear()

    for _ in range(repo.LOCKOUT_MAX_ATTEMPTS):
        r = c.post("/auth/login", json={"email": "lock@y.com", "password": "wrong"})
        assert r.status_code == 401

    r = c.post("/auth/login", json={"email": "lock@y.com", "password": "password123"})
    assert r.status_code == 423


def test_successful_login_resets_counter(client):
    c, conn = client
    c.post("/auth/register", json={
        "email": "reset@y.com", "name": "R", "password": "password123"})
    c.cookies.clear()

    c.post("/auth/login", json={"email": "reset@y.com", "password": "wrong"})
    c.post("/auth/login", json={"email": "reset@y.com", "password": "wrong"})
    r = c.post("/auth/login", json={"email": "reset@y.com", "password": "password123"})
    assert r.status_code == 200

    user = repo.get_user_by_email(conn, "reset@y.com")
    assert user["failed_login_attempts"] == 0
    assert user["locked_until"] is None
