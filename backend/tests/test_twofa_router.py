import sqlite3

import pyotp
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.conn import get_conn
from auth.dependencies import get_current_user
from db import init_schema, seed_mock_users
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
        conn.execute("SELECT * FROM users WHERE email='demo@foroba.app'").fetchone()
    )
    app.include_router(router)
    return TestClient(app), conn


def test_enroll_returns_qr_and_secret(client):
    c, conn = client
    r = c.post("/auth/2fa/enroll")
    assert r.status_code == 200
    body = r.json()
    assert body["qr"].startswith("data:image/png;base64,")
    assert conn.execute("SELECT totp_secret FROM users WHERE email='demo@foroba.app'").fetchone()[
        "totp_secret"
    ]


def test_verify_enables(client):
    c, conn = client
    c.post("/auth/2fa/enroll")
    secret = conn.execute("SELECT totp_secret FROM users WHERE email='demo@foroba.app'").fetchone()[
        "totp_secret"
    ]
    code = pyotp.TOTP(secret).now()
    r = c.post("/auth/2fa/verify", json={"code": code})
    assert r.status_code == 200
    assert (
        conn.execute("SELECT totp_enabled FROM users WHERE email='demo@foroba.app'").fetchone()[
            "totp_enabled"
        ]
        == 1
    )


def test_verify_clears_mfa_enrollment_pending(client):
    """foroba#173 — enrolling any method clears the forced-setup flag from registration."""
    c, conn = client
    conn.execute("UPDATE users SET mfa_enrollment_pending = 1 WHERE email='demo@foroba.app'")
    conn.commit()
    c.post("/auth/2fa/enroll")
    secret = conn.execute("SELECT totp_secret FROM users WHERE email='demo@foroba.app'").fetchone()[
        "totp_secret"
    ]
    code = pyotp.TOTP(secret).now()
    r = c.post("/auth/2fa/verify", json={"code": code})
    assert r.status_code == 200
    assert (
        conn.execute(
            "SELECT mfa_enrollment_pending FROM users WHERE email='demo@foroba.app'"
        ).fetchone()["mfa_enrollment_pending"]
        == 0
    )


def test_verify_rejects_bad_code(client):
    c, _conn = client
    c.post("/auth/2fa/enroll")
    r = c.post("/auth/2fa/verify", json={"code": "000000"})
    assert r.status_code == 400


def test_methods_lists_all_flags_and_recovery_count(client):
    c, _conn = client
    resp = c.get("/auth/2fa/methods")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {
        "totp_enabled",
        "email_otp_enabled",
        "webauthn_enabled",
        "recovery_codes_remaining",
    }


def test_remove_last_method_is_blocked(client):
    c, conn = client
    c.post("/auth/2fa/enroll")
    secret = conn.execute(
        "SELECT totp_secret FROM users WHERE email='demo@foroba.app'"
    ).fetchone()["totp_secret"]
    code = pyotp.TOTP(secret).now()
    c.post("/auth/2fa/verify", json={"code": code})
    resp = c.delete("/auth/2fa/methods/totp")
    assert resp.status_code == 400


def test_recovery_codes_regenerate_returns_ten_codes(client):
    c, _conn = client
    resp = c.post("/auth/2fa/recovery-codes/regenerate")
    assert resp.status_code == 200
    assert len(resp.json()["codes"]) == 10


def test_email_otp_send_requires_smtp(client, monkeypatch):
    from config import settings

    c, _conn = client
    monkeypatch.setattr(settings, "smtp_enabled", False)
    resp = c.post("/auth/2fa/email-otp/send")
    assert resp.status_code == 503


def test_methods_returns_defaults_for_synthetic_dev_bypass_user():
    """AUTH_DEV_BYPASS's synthetic user (id=0) has no row in `users` — /methods must not
    500 when repo.get_user_by_id() legitimately returns None for it, it should report
    nothing-enrolled defaults instead (mirrors the real behavior for that user)."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: {"id": 0, "email": "dev@localhost.dev"}
    app.include_router(router)
    c = TestClient(app)

    resp = c.get("/auth/2fa/methods")

    assert resp.status_code == 200
    assert resp.json() == {
        "totp_enabled": False,
        "email_otp_enabled": False,
        "webauthn_enabled": False,
        "recovery_codes_remaining": 0,
    }
