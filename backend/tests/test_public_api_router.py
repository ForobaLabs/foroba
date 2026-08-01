"""Route tests for GET /api/public/v1/* — API-key auth path, incl. gating (foroba#165,
TI-D item 5, Plan A)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import db
from auth.conn import get_conn
from auth.security import hash_password
from main import app
from settings_store import init_settings, set_value


def _memory_conn():
    c = db.connect(":memory:")
    init_settings(c)
    set_value(c, "premium_gating_enabled", "true")
    return c


def _seed_user_and_key(conn, *, tier="premium", audience="base") -> str:
    cur = conn.execute(
        "INSERT INTO users (email, name, password_hash, tier, audience) VALUES (?, ?, ?, ?, ?)",
        (f"{tier}-{audience}@test.local", "U", "x", tier, audience),
    )
    conn.commit()
    user_id = cur.lastrowid
    secret = "test-secret-value"
    prefix = f"fpk_{tier}{audience}"
    db.create_api_key(
        conn, user_id=user_id, label="test", key_prefix=prefix, secret_hash=hash_password(secret)
    )
    return f"{prefix}.{secret}"


async def _fake_fetch_networth(days, *, cookie=None):
    return {
        "bank": None,
        "investments": None,
        "total_eur": 0.0,
        "history": [],
        "degraded": True,
        "disclaimer": "x",
    }


async def _fake_generate_notifications(conn, user_id, *, cookie=None):
    return {"items": [], "degraded": False}


def test_networth_requires_api_key(monkeypatch):
    import networth_service as nws

    monkeypatch.setattr(nws, "fetch_networth", _fake_fetch_networth)
    conn = _memory_conn()
    app.dependency_overrides[get_conn] = lambda: conn
    try:
        client = TestClient(app)
        resp = client.get("/api/public/v1/networth")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_conn, None)


def test_networth_returns_402_for_free_tier_key(monkeypatch):
    import networth_service as nws

    monkeypatch.setattr(nws, "fetch_networth", _fake_fetch_networth)
    conn = _memory_conn()
    key = _seed_user_and_key(conn, tier="free")
    app.dependency_overrides[get_conn] = lambda: conn
    try:
        client = TestClient(app)
        resp = client.get("/api/public/v1/networth", headers={"Authorization": f"Bearer {key}"})
        assert resp.status_code == 402
    finally:
        app.dependency_overrides.pop(get_conn, None)


def test_networth_returns_200_with_valid_premium_key(monkeypatch):
    import networth_service as nws

    monkeypatch.setattr(nws, "fetch_networth", _fake_fetch_networth)
    conn = _memory_conn()
    key = _seed_user_and_key(conn, tier="premium")
    app.dependency_overrides[get_conn] = lambda: conn
    try:
        client = TestClient(app)
        resp = client.get("/api/public/v1/networth", headers={"Authorization": f"Bearer {key}"})
        assert resp.status_code == 200
        assert resp.json()["disclaimer"] == "x"
    finally:
        app.dependency_overrides.pop(get_conn, None)


def test_notifications_returns_200_with_valid_premium_key(monkeypatch):
    import notification_service as ns

    monkeypatch.setattr(ns, "generate_notifications", _fake_generate_notifications)
    conn = _memory_conn()
    key = _seed_user_and_key(conn, tier="premium")
    app.dependency_overrides[get_conn] = lambda: conn
    try:
        client = TestClient(app)
        resp = client.get(
            "/api/public/v1/notifications", headers={"Authorization": f"Bearer {key}"}
        )
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "degraded": False}
    finally:
        app.dependency_overrides.pop(get_conn, None)
