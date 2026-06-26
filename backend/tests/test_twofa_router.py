import sqlite3

import pyotp
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from db import init_schema, seed_mock_users
from auth.conn import get_conn
from auth.dependencies import get_current_user
from twofa.router import router


@pytest.fixture
def client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    seed_mock_users(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: dict(
        conn.execute("SELECT * FROM users WHERE email='demo@foroba.app'").fetchone())
    app.include_router(router)
    return TestClient(app), conn


def test_enroll_returns_qr_and_secret(client):
    c, conn = client
    r = c.post("/auth/2fa/enroll")
    assert r.status_code == 200
    body = r.json()
    assert body["qr"].startswith("data:image/png;base64,")
    assert conn.execute(
        "SELECT totp_secret FROM users WHERE email='demo@foroba.app'"
    ).fetchone()["totp_secret"]


def test_verify_enables(client):
    c, conn = client
    c.post("/auth/2fa/enroll")
    secret = conn.execute(
        "SELECT totp_secret FROM users WHERE email='demo@foroba.app'"
    ).fetchone()["totp_secret"]
    code = pyotp.TOTP(secret).now()
    r = c.post("/auth/2fa/verify", json={"code": code})
    assert r.status_code == 200
    assert conn.execute(
        "SELECT totp_enabled FROM users WHERE email='demo@foroba.app'"
    ).fetchone()["totp_enabled"] == 1


def test_verify_rejects_bad_code(client):
    c, conn = client
    c.post("/auth/2fa/enroll")
    r = c.post("/auth/2fa/verify", json={"code": "000000"})
    assert r.status_code == 400
