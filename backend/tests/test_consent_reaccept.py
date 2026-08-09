"""CL-2.1 — Consent re-acceptance enforcement on legal version bump (foroba#238)."""
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.router import get_conn, router
from db import init_schema
from rate_limit import limiter
from settings_store import init_settings

_REG = {
    "email": "consent@y.com",
    "email_confirm": "consent@y.com",
    "name": "Consent",
    "password": "password123",
    "password_confirm": "password123",
    "tos_accepted": True,
}


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    init_settings(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(router)
    return TestClient(app)


def test_status_flags_current_consent(client):
    """After signup the user has accepted current versions — both True."""
    r = client.post("/auth/register", json=_REG)
    assert r.status_code == 201, r.text
    r = client.get("/auth/consents/status")
    assert r.status_code == 200
    body = r.json()
    assert body["terms_of_service"] is True
    assert body["privacy_policy"] is True


def test_status_flags_stale_when_version_bumped(client, monkeypatch):
    """After a legal version bump the TOS flag becomes False."""
    r = client.post("/auth/register", json=_REG)
    assert r.status_code == 201, r.text
    monkeypatch.setattr("auth.router.TOS_VERSION", "2999-01-01")
    r = client.get("/auth/consents/status")
    assert r.status_code == 200
    assert r.json()["terms_of_service"] is False
    assert r.json()["privacy_policy"] is True  # PP unchanged


def test_accept_records_new_consent(client, monkeypatch):
    """POST /auth/consents/accept re-records the bumped version and status returns True."""
    r = client.post("/auth/register", json=_REG)
    assert r.status_code == 201, r.text
    monkeypatch.setattr("auth.router.TOS_VERSION", "2999-01-01")
    assert client.post(
        "/auth/consents/accept", json={"documents": ["terms_of_service"]}
    ).status_code == 204
    assert client.get("/auth/consents/status").json()["terms_of_service"] is True


def test_accept_unknown_document_is_400(client):
    r = client.post("/auth/register", json=_REG)
    assert r.status_code == 201, r.text
    r = client.post("/auth/consents/accept", json={"documents": ["unknown_doc"]})
    assert r.status_code == 400
