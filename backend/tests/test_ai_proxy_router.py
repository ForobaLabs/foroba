"""Plan AV T7 — /ai/* proxy to the gateway + GDPR export/erase hooks."""

import logging
import sqlite3

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

import ai_proxy_router
import settings_store
from auth import repository as repo
from auth.dependencies import get_current_user
from auth.router import get_conn
from auth.router import router as auth_router
from config import settings
from db import init_schema
from rate_limit import limiter

BASE = "http://gw.test"
USER = {"id": 7, "email": "u7@test.local", "is_admin": False}
ADMIN = {"id": 1, "email": "a@test.local", "is_admin": True}


@pytest.fixture(autouse=True)
def _gateway_settings(monkeypatch):
    monkeypatch.setattr(settings, "ai_gateway_url", BASE)
    monkeypatch.setattr(settings, "ai_gateway_token", "s3cret-token")
    monkeypatch.delenv("AUTH_DEV_BYPASS", raising=False)
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    init_schema(c)
    settings_store.init_settings(c)
    return c


@pytest.fixture
def client(conn):
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: USER
    app.include_router(ai_proxy_router.router)
    return TestClient(app, raise_server_exceptions=False)


AUTH = {"Authorization": "Bearer jwt.abc.def"}


@respx.mock
def test_proxy_forwards_jwt_and_token(client):
    route = respx.get(f"{BASE}/v1/prefs").mock(return_value=httpx.Response(200, json={"prefs": []}))
    r = client.get("/ai/prefs", headers=AUTH)
    assert r.status_code == 200 and r.json() == {"prefs": []}
    sent = route.calls[0].request
    assert sent.headers["authorization"] == "Bearer jwt.abc.def"
    assert sent.headers["x-ai-gateway-token"] == "s3cret-token"


@respx.mock
def test_proxy_forwards_cookie_session_as_bearer(client):
    route = respx.get(f"{BASE}/v1/usage").mock(return_value=httpx.Response(200, json={}))
    client.cookies.set("suite_session", "cookie.jwt.value")
    assert client.get("/ai/usage").status_code == 200
    assert route.calls[0].request.headers["authorization"] == "Bearer cookie.jwt.value"


def test_proxy_requires_auth_401():
    app = FastAPI()
    app.include_router(ai_proxy_router.router)
    r = TestClient(app).get("/ai/prefs")
    assert r.status_code == 401


@respx.mock
def test_proxy_put_prefs_and_204_delete(client):
    respx.put(f"{BASE}/v1/prefs").mock(return_value=httpx.Response(200, json={"ok": True}))
    respx.delete(f"{BASE}/v1/consents/byok:openai").mock(return_value=httpx.Response(204))
    respx.delete(f"{BASE}/v1/byok/openai").mock(return_value=httpx.Response(204))
    respx.post(f"{BASE}/v1/byok/openai/test").mock(
        return_value=httpx.Response(200, json={"ok": True, "status": "valid"})
    )
    assert client.put("/ai/prefs", json={"app": "foroba"}, headers=AUTH).json() == {"ok": True}
    assert client.delete("/ai/consents/byok:openai", headers=AUTH).status_code == 204
    assert client.delete("/ai/byok/openai", headers=AUTH).status_code == 204
    assert client.post("/ai/byok/openai/test", headers=AUTH).json()["status"] == "valid"


@respx.mock
def test_gateway_down_gives_503_code(client):
    respx.get(f"{BASE}/v1/prefs").mock(side_effect=httpx.ConnectError("down"))
    r = client.get("/ai/prefs", headers=AUTH)
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "ai_gateway_unavailable"


@respx.mock
def test_byok_save_rejection_passes_code_through(client):
    respx.put(f"{BASE}/v1/byok").mock(
        return_value=httpx.Response(422, json={"detail": {"code": "byok_test_failed"}})
    )
    r = client.put(
        "/ai/byok", json={"provider": "openai", "api_key": "sk-secret-123456"}, headers=AUTH
    )
    assert r.status_code == 422
    assert r.json() == {"detail": {"code": "byok_test_failed"}}
    assert "sk-secret-123456" not in r.text


@respx.mock
def test_byok_put_body_not_logged(client, caplog):
    respx.put(f"{BASE}/v1/byok").mock(return_value=httpx.Response(200, json={"last4": "3456"}))
    with caplog.at_level(logging.DEBUG):
        client.put(
            "/ai/byok", json={"provider": "openai", "api_key": "sk-secret-123456"}, headers=AUTH
        )
    assert "sk-secret-123456" not in caplog.text


@respx.mock
def test_admin_usage_requires_admin(conn):
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: USER
    app.include_router(ai_proxy_router.router)
    c = TestClient(app)
    assert c.get("/ai/admin/usage?month=2026-10", headers=AUTH).status_code == 403
    route = respx.get(f"{BASE}/v1/admin/usage").mock(
        return_value=httpx.Response(200, json={"month": "2026-10"})
    )
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    r = c.get("/ai/admin/usage?month=2026-10", headers=AUTH)
    assert r.status_code == 200
    assert route.calls[0].request.url.params["month"] == "2026-10"


# ── GDPR hooks in auth/router.py ────────────────────────────────────────────

_REG = {
    "email": "ai@y.com",
    "email_confirm": "ai@y.com",
    "name": "AI",
    "password": "password12345",
    "password_confirm": "password12345",
    "tos_accepted": True,
}


@pytest.fixture
def auth_client(conn):
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(auth_router)
    return TestClient(app, raise_server_exceptions=False)


def _register(c):
    assert c.post("/auth/register", json=_REG).status_code == 201


@respx.mock
def test_export_includes_ai_section(auth_client):
    _register(auth_client)
    uid = auth_client.get("/auth/me").json()["id"]
    respx.get(f"{BASE}/v1/users/{uid}/export").mock(
        return_value=httpx.Response(200, json={"consents": [{"provider": "cloudflare"}]})
    )
    respx.get(url__regex=r"http://localhost:(8000|8050)/account/export").mock(
        return_value=httpx.Response(200, json={})
    )
    body = auth_client.get("/auth/account/export").json()
    assert body["ai"] == {"consents": [{"provider": "cloudflare"}]}


@respx.mock
def test_export_gateway_down_marks_unavailable(auth_client):
    _register(auth_client)
    uid = auth_client.get("/auth/me").json()["id"]
    respx.get(f"{BASE}/v1/users/{uid}/export").mock(side_effect=httpx.ConnectError("down"))
    respx.get(url__regex=r"http://localhost:(8000|8050)/account/export").mock(
        return_value=httpx.Response(200, json={})
    )
    assert auth_client.get("/auth/account/export").json()["ai"] == {"unavailable": True}


def _erase_mocks():
    respx.delete(url__regex=r"http://localhost:(8000|8050)/account/erase").mock(
        return_value=httpx.Response(204)
    )


@respx.mock
def test_delete_account_calls_gateway_delete(auth_client, conn):
    _register(auth_client)
    uid = auth_client.get("/auth/me").json()["id"]
    _erase_mocks()
    gw = respx.delete(f"{BASE}/v1/users/{uid}").mock(return_value=httpx.Response(204))
    r = auth_client.request("DELETE", "/auth/account", json={"password": "password12345"})
    assert r.status_code == 204, r.text
    assert gw.called
    assert gw.calls[0].request.headers["x-ai-gateway-token"] == "s3cret-token"
    assert repo.get_user_by_id(conn, uid) is None


@respx.mock
def test_delete_account_gateway_down_records_pending(auth_client, conn, caplog):
    _register(auth_client)
    uid = auth_client.get("/auth/me").json()["id"]
    _erase_mocks()
    respx.delete(f"{BASE}/v1/users/{uid}").mock(side_effect=httpx.ConnectError("down"))
    with caplog.at_level(logging.WARNING):
        r = auth_client.request("DELETE", "/auth/account", json={"password": "password12345"})
    assert r.status_code == 204, r.text
    assert repo.get_user_by_id(conn, uid) is None
    assert f"ai_gateway_delete_pending user_id={uid}" in caplog.text
    assert [r[0] for r in conn.execute("SELECT user_id FROM ai_gateway_pending_deletes")] == [uid]


@respx.mock
@pytest.mark.parametrize(
    "path",
    [
        "/ai/consents/..%2Fusers%2F5",
        "/ai/consents/%2E%2E/users/5",
        "/ai/consents/x/..%2F..%2Fusers%2F5",
        "/ai/byok/..",
        "/ai/byok/../test",
    ],
)
def test_provider_path_traversal_never_reaches_gateway(client, path):
    """PB-013: a `../` provider must not turn into a gateway-token call on /v1/users/{id}."""
    erase = respx.delete(f"{BASE}/v1/users/5").mock(return_value=httpx.Response(204))
    catch_all = respx.route().mock(return_value=httpx.Response(204))
    method = client.post if path.endswith("/test") else client.delete
    r = method(path, headers=AUTH)
    assert r.status_code in (400, 404, 405, 422)
    assert not erase.called and not catch_all.called
