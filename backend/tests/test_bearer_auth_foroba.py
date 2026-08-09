"""T5: Foroba get_current_user accepts Authorization: Bearer <jwt>."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from auth import keys
from auth.conn import get_conn
from auth.router import router as auth_router
from auth.security import create_token
from config import settings
from db import init_schema
from rate_limit import limiter
from settings_store import init_settings


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
    conn.execute(
        "INSERT INTO users (id, email, name, password_hash) VALUES (1, 't@t.com', 'T', 'x')"
    )
    conn.commit()
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(auth_router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def valid_session_token():
    private_key, _, kid = keys.get_keypair(settings)
    return create_token(1, private_key, settings.jwt_ttl_minutes, kid=kid)


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_bearer_token_authenticates(client, valid_session_token):
    resp = client.get("/auth/me", headers=_bearer(valid_session_token))
    assert resp.status_code == status.HTTP_200_OK


def test_cookie_still_authenticates(client, valid_session_token):
    client.cookies.set("suite_session", valid_session_token)
    resp = client.get("/auth/me")
    assert resp.status_code == status.HTTP_200_OK


def test_bearer_takes_precedence_over_a_stale_cookie(client, valid_session_token):
    client.cookies.set("suite_session", "garbage")
    resp = client.get("/auth/me", headers=_bearer(valid_session_token))
    assert resp.status_code == status.HTTP_200_OK


def test_malformed_bearer_is_rejected(client):
    resp = client.get("/auth/me", headers=_bearer("not-a-jwt"))
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_missing_credentials_are_rejected(client):
    resp = client.get("/auth/me")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("header", ["", "Bearer", "Basic abc", "Bearer  "])
def test_non_bearer_headers_fall_through_to_cookie(client, header):
    resp = client.get("/auth/me", headers={"Authorization": header})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
