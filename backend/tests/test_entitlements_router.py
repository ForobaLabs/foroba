import sqlite3

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from db import init_schema, seed_mock_users
from auth.router import get_conn
from auth.dependencies import get_current_user
from auth.entitlements_router import router, require_feature
from settings_store import init_settings, set_value


@pytest.fixture
def app_conn():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    seed_mock_users(conn)
    init_settings(conn)
    # Enable gating so entitlement checks are active in these tests
    set_value(conn, "premium_gating_enabled", "true")
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn

    def _as(email):
        return lambda: dict(conn.execute(
            "SELECT * FROM users WHERE email=?", (email,)).fetchone())

    app.include_router(router)

    @app.get("/needs-backtest")
    def needs(_=Depends(require_feature("markets.backtesting"))):
        return {"ok": True}

    return app, conn, _as


def test_entitlements_lists_registry(app_conn):
    app, conn, _as = app_conn
    app.dependency_overrides[get_current_user] = _as("demo@foroba.app")
    c = TestClient(app)
    r = c.get("/auth/entitlements")
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["tier"] == "free"
    assert body["features"]["markets.backtesting"]["visible"] is False


def test_require_feature_402_for_free_user(app_conn):
    app, conn, _as = app_conn
    app.dependency_overrides[get_current_user] = _as("demo@foroba.app")
    c = TestClient(app)
    r = c.get("/needs-backtest")
    assert r.status_code in (402, 403)


def test_require_feature_allows_premium(app_conn):
    app, conn, _as = app_conn
    app.dependency_overrides[get_current_user] = _as("pro@foroba.app")
    c = TestClient(app)
    assert c.get("/needs-backtest").status_code == 200
