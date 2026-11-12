"""CL-2.2 — DSAR: portability export + processing-restriction/objection flags (foroba#239)."""
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.router import get_conn, router
from db import init_schema
from rate_limit import limiter
from settings_store import init_settings

_REG = {
    "email": "dsar@y.com",
    "email_confirm": "dsar@y.com",
    "name": "DSAR",
    "password": "password12345",
    "password_confirm": "password12345",
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
    return TestClient(app, raise_server_exceptions=False)


def test_export_returns_foroba_bundle(client):
    """GET /account/export returns at minimum a foroba section with profile + consents."""
    r = client.post("/auth/register", json=_REG)
    assert r.status_code == 201, r.text
    # Export endpoint calls pazuru/tsumi cross-app — those aren't wired in the test
    # client, so we only assert the foroba section keys exist (cross-app parts absent/null).
    r = client.get("/auth/account/export")
    assert r.status_code == 200
    body = r.json()
    assert "foroba" in body
    assert "profile" in body["foroba"]
    assert "consents" in body["foroba"]
    assert body["foroba"]["profile"]["email"] == "dsar@y.com"


def test_processing_restriction_flag(client):
    r = client.post("/auth/register", json=_REG)
    assert r.status_code == 201, r.text
    r = client.put("/auth/me/processing", json={"processing_restricted": True})
    assert r.status_code == 204, r.text
    me = client.get("/auth/me").json()
    assert me["processing_restricted"] is True


def test_marketing_objection_flag(client):
    r = client.post("/auth/register", json=_REG)
    assert r.status_code == 201, r.text
    r = client.put("/auth/me/processing", json={"marketing_objection": True})
    assert r.status_code == 204, r.text
    me = client.get("/auth/me").json()
    assert me["marketing_objection"] is True


def test_export_profile_never_contains_credentials_or_secrets(client):
    client.post("/auth/register", json=_REG)
    profile = client.get("/auth/account/export").json()["foroba"]["profile"]
    leaked = {"password_hash", "totp_secret", "totp_secret_pending", "session_version"} & set(
        profile
    )
    assert leaked == set()
