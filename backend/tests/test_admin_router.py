import sqlite3
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from admin_router import router as admin_router
from auth.conn import get_conn
from auth.dependencies import get_current_user
from db import connect, seed_mock_users
from settings_store import init_settings


@pytest.fixture
def setup(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = connect(db_path)
    seed_mock_users(conn)
    init_settings(conn)

    admin_user = dict(conn.execute(
        "SELECT * FROM users WHERE email = ?", ("admin@foroba.app",)
    ).fetchone())
    regular_user = dict(conn.execute(
        "SELECT * FROM users WHERE email = ?", ("demo@foroba.app",)
    ).fetchone())

    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_conn] = lambda: conn

    return TestClient(app), conn, admin_user, regular_user


def test_get_settings_public_no_auth(setup):
    tc, conn, _, _ = setup
    resp = tc.get("/jeli/admin/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "premium_gating_enabled" in data


def test_get_admin_settings_requires_admin(setup):
    tc, conn, _, regular = setup
    tc.app.dependency_overrides[get_current_user] = lambda: regular
    resp = tc.get("/admin/settings")
    assert resp.status_code == 403


def test_get_admin_settings_admin_ok(setup):
    tc, conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin
    resp = tc.get("/admin/settings")
    assert resp.status_code == 200


def test_patch_admin_setting(setup):
    tc, conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin
    resp = tc.patch(
        "/admin/settings/premium_gating_enabled",
        json={"value": "true"},
    )
    assert resp.status_code == 200
    resp2 = tc.get("/jeli/admin/settings")
    assert resp2.json()["premium_gating_enabled"] == "true"


def test_patch_invalid_value_returns_422(setup):
    tc, conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin
    resp = tc.patch(
        "/admin/settings/premium_gating_enabled",
        json={"value": "yes"},
    )
    assert resp.status_code == 422


def test_get_admin_users_returns_list(setup):
    tc, conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin
    resp = tc.get("/admin/users")
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    assert any(u["email"] == "admin@foroba.app" for u in users)
