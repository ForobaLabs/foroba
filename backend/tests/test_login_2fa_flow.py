import sqlite3

import pyotp
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import config
from db import init_schema, seed_mock_users
from auth.router import router as auth_router
from auth.conn import get_conn
from auth import repository as repo


def _client(monkeypatch, flag: bool):
    monkeypatch.setattr(config.settings, "auth_2fa_enabled", flag, raising=False)
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    seed_mock_users(conn)
    # Enable 2FA for demo user
    secret = "JBSWY3DPEHPK3PXP"
    demo = repo.get_user_by_email(conn, "demo@foroba.app")
    repo.set_totp_secret(conn, demo["id"], secret)
    repo.enable_totp(conn, demo["id"])
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(auth_router)
    return TestClient(app), secret


def test_login_challenges_when_flag_on(monkeypatch):
    c, secret = _client(monkeypatch, True)
    r = c.post("/auth/login", json={"email": "demo@foroba.app", "password": "Demo!2026"})
    assert r.status_code == 200
    assert r.json().get("mfa_required") is True
    assert not c.cookies.get("suite_session")  # no session yet
    code = pyotp.TOTP(secret).now()
    r2 = c.post("/auth/login/2fa", json={"email": "demo@foroba.app", "code": code})
    assert r2.status_code == 200
    assert c.cookies.get("suite_session")


def test_login_ignores_2fa_when_flag_off(monkeypatch):
    c, _ = _client(monkeypatch, False)
    r = c.post("/auth/login", json={"email": "demo@foroba.app", "password": "Demo!2026"})
    assert r.status_code == 200
    assert r.json().get("mfa_required") in (None, False)
    assert c.cookies.get("suite_session")  # logged in directly
