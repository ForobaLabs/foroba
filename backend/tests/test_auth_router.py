import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import repository as repo
from auth.dependencies import get_current_user
from auth.router import get_conn, router
from auth.security import hash_password
from db import init_schema
from rate_limit import limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # /auth/register is rate-limited (5/minute), shared across the whole test
    # session since `limiter` is a module-level singleton — this file alone
    # calls /auth/register more than 5 times, so reset between tests.
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
            "tos_accepted": True,
        },
    )
    assert r.status_code == 201, r.text
    assert client.cookies.get("suite_session")

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "x@y.com"


def test_register_requires_tos_acceptance(client):
    r = client.post(
        "/auth/register",
        json={
            "email": "notos@y.com",
            "email_confirm": "notos@y.com",
            "name": "No Tos",
            "password": "password123",
            "password_confirm": "password123",
            "tos_accepted": False,
        },
    )
    assert r.status_code == 422


def test_register_records_consents_and_exposes_them(client):
    r = client.post(
        "/auth/register",
        json={
            "email": "consentflow@y.com",
            "email_confirm": "consentflow@y.com",
            "name": "Consent Flow",
            "password": "password123",
            "password_confirm": "password123",
            "tos_accepted": True,
        },
    )
    assert r.status_code == 201

    consents = client.get("/auth/consents")
    assert consents.status_code == 200
    body = consents.json()
    assert len(body) == 2
    types = {c["document_type"] for c in body}
    assert types == {"terms_of_service", "privacy_policy"}
    for c in body:
        assert c["document_version"]
        assert c["accepted_at"]


def test_login_wrong_password_401(client):
    client.post(
        "/auth/register",
        json={
            "email": "x@y.com",
            "email_confirm": "x@y.com",
            "name": "X",
            "password": "password123",
            "password_confirm": "password123",
            "tos_accepted": True,
        },
    )
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
            "tos_accepted": True,
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


def test_login_sets_cookie_domain_when_configured(client, monkeypatch):
    # Smoke test that registration still succeeds and issues a cookie when cookie_domain is
    # set to a foreign domain. NOTE: we can't assert via client.cookies.get() here — httpx's
    # TestClient cookie jar won't store cookies scoped to a domain that doesn't match the
    # "testserver" host it requests against, regardless of correctness (see the precise
    # raw-header assertion in test_login_cookie_domain_attribute_present below).
    from config import settings

    monkeypatch.setattr(settings, "cookie_domain", ".pfh.example.com")
    resp = client.post(
        "/auth/register",
        json={
            "email": "domaincookie@example.com",
            "email_confirm": "domaincookie@example.com",
            "name": "Domain Cookie",
            "password": "Sup3rSecret!",
            "password_confirm": "Sup3rSecret!",
            "tos_accepted": True,
        },
    )
    assert resp.status_code == 201
    assert resp.headers.get("set-cookie") is not None


def test_login_cookie_domain_attribute_present(client, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "cookie_domain", ".pfh.example.com")
    resp = client.post(
        "/auth/register",
        json={
            "email": "domaincookie2@example.com",
            "email_confirm": "domaincookie2@example.com",
            "name": "Domain Cookie2",
            "password": "Sup3rSecret!",
            "password_confirm": "Sup3rSecret!",
            "tos_accepted": True,
        },
    )
    if hasattr(resp.headers, "get_list"):
        raw_cookie_headers = resp.headers.get_list("set-cookie")
    else:
        raw_cookie_headers = [resp.headers.get("set-cookie", "")]
    assert any("Domain=.pfh.example.com" in h for h in raw_cookie_headers)
