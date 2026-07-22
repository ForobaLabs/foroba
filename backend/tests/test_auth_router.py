import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import init_schema
import auth.dependencies as deps
from auth.router import router, get_conn


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
    r = client.post("/auth/register", json={
        "email": "x@y.com", "name": "X", "password": "password123"})
    assert r.status_code == 201, r.text
    assert client.cookies.get("suite_session")

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "x@y.com"


def test_login_wrong_password_401(client):
    client.post("/auth/register", json={
        "email": "x@y.com", "name": "X", "password": "password123"})
    r = client.post("/auth/login", json={"email": "x@y.com", "password": "nope"})
    assert r.status_code == 401


def test_me_without_cookie_401(client):
    assert client.get("/auth/me").status_code == 401


def test_update_display_currency(client):
    register = client.post("/auth/register", json={
        "email": "curr@y.com", "name": "Curr User", "password": "password123"})
    assert register.status_code == 201

    resp = client.put("/auth/me/currency", json={"display_currency": "USD"})
    assert resp.status_code == 204

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["display_currency"] == "USD"
