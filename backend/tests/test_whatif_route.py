"""Route tests for /whatif/* (service + db mocked, foroba#162)."""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

import whatif_service as ws
from auth.conn import get_conn
from auth.dependencies import get_current_user
from db import init_schema
from main import app
from settings_store import init_settings, set_value

_PREMIUM_USER = {
    "id": 1,
    "email": "u1@test.local",
    "tier": "premium",
    "audience": "expert",
    "household_id": None,
    "is_admin": False,
}
_FREE_USER = {
    "id": 2,
    "email": "u2@test.local",
    "tier": "free",
    "audience": "expert",
    "household_id": None,
    "is_admin": False,
}


async def _fake_simulate(params, horizon_months, *, owner_cookie=None, **_):
    return {
        "points": [
            {
                "month": 1,
                "resolution": "monthly",
                "bank_eur": 1.0,
                "investments_eur": 0.0,
                "total_eur": 1.0,
            }
        ],
        "goal_impacts": [],
        "degraded": False,
        "disclaimer": ws.DISCLAIMER,
    }


def _override_user(user):
    # Gate on an isolated in-memory DB with gating explicitly enabled — the
    # real dev DB may have premium_gating_enabled=false (demo mode), which
    # would make require_feature always pass and hide the 402 case.
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    init_settings(conn)
    set_value(conn, "premium_gating_enabled", "true")
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: user


def test_simulate_requires_premium(monkeypatch):
    monkeypatch.setattr(ws, "simulate", _fake_simulate)
    _override_user(_FREE_USER)
    try:
        client = TestClient(app)
        resp = client.post("/whatif/simulate", json={"horizon_months": 1})
        assert resp.status_code == 402
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_conn, None)


def test_simulate_returns_projection(monkeypatch):
    monkeypatch.setattr(ws, "simulate", _fake_simulate)
    _override_user(_PREMIUM_USER)
    try:
        client = TestClient(app)
        resp = client.post("/whatif/simulate", json={"horizon_months": 1})
        assert resp.status_code == 200
        assert resp.json()["points"][0]["month"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_conn, None)


def test_simulate_rejects_negative_horizon_months(monkeypatch):
    monkeypatch.setattr(ws, "simulate", _fake_simulate)
    _override_user(_PREMIUM_USER)
    try:
        client = TestClient(app)
        resp = client.post("/whatif/simulate", json={"horizon_months": -5})
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_conn, None)


def test_simulate_rejects_zero_horizon_months(monkeypatch):
    monkeypatch.setattr(ws, "simulate", _fake_simulate)
    _override_user(_PREMIUM_USER)
    try:
        client = TestClient(app)
        resp = client.post("/whatif/simulate", json={"horizon_months": 0})
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_conn, None)


def test_scenario_crud_roundtrip(monkeypatch):
    monkeypatch.setattr(ws, "simulate", _fake_simulate)
    _override_user(_PREMIUM_USER)
    try:
        client = TestClient(app)
        create = client.post(
            "/whatif/scenarios",
            json={
                "name": "Test scenario",
                "horizon_months": 12,
                "params": {"horizon_months": 12},
            },
        )
        assert create.status_code == 201
        scenario_id = create.json()["id"]

        listed = client.get("/whatif/scenarios")
        assert any(s["id"] == scenario_id for s in listed.json())

        fetched = client.get(f"/whatif/scenarios/{scenario_id}")
        assert fetched.status_code == 200
        assert fetched.json()["projection"]["points"][0]["month"] == 1

        updated = client.put(
            f"/whatif/scenarios/{scenario_id}",
            json={
                "name": "Renamed",
                "horizon_months": 24,
                "params": {"horizon_months": 24},
            },
        )
        assert updated.json()["name"] == "Renamed"

        deleted = client.delete(f"/whatif/scenarios/{scenario_id}")
        assert deleted.status_code == 204
        assert client.get(f"/whatif/scenarios/{scenario_id}").status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_conn, None)
