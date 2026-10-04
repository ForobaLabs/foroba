import sqlite3
from typing import ClassVar

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import repository as repo
from auth.dependencies import get_current_user
from auth.router import get_conn, router
from auth.security import hash_password
from db import init_schema
from rate_limit import limiter
from settings_store import init_settings


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # /auth/register is rate-limited (5/minute), shared across the whole test
    # session since `limiter` is a module-level singleton — this file alone
    # calls /auth/register more than 5 times, so reset between tests.
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
    return TestClient(app)


def test_register_then_me(client):
    r = client.post(
        "/auth/register",
        json={
            "email": "x@y.com",
            "email_confirm": "x@y.com",
            "name": "X",
            "password": "password123",
            "password_confirm": "password123",
            "tos_accepted": True,
        },
    )
    assert r.status_code == 201, r.text
    assert client.cookies.get("suite_session")

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "x@y.com"


def test_register_sets_mfa_enrollment_pending(client):
    """foroba#173 — new self-service signups must be forced through MFA enrollment."""
    r = client.post(
        "/auth/register",
        json={
            "email": "pending@y.com",
            "email_confirm": "pending@y.com",
            "name": "Pending",
            "password": "password123",
            "password_confirm": "password123",
            "tos_accepted": True,
        },
    )
    assert r.status_code == 201
    assert r.json()["mfa_enrollment_pending"] is True

    me = client.get("/auth/me")
    assert me.json()["mfa_enrollment_pending"] is True


def test_register_requires_tos_acceptance(client):
    r = client.post(
        "/auth/register",
        json={
            "email": "notos@y.com",
            "email_confirm": "notos@y.com",
            "name": "No Tos",
            "password": "password123",
            "password_confirm": "password123",
            "tos_accepted": False,
        },
    )
    assert r.status_code == 422


def test_register_without_invite_code_when_flag_off_succeeds(client):
    r = client.post(
        "/auth/register",
        json={
            "email": "openreg@y.com",
            "email_confirm": "openreg@y.com",
            "name": "Open Reg",
            "password": "password123",
            "password_confirm": "password123",
            "tos_accepted": True,
        },
    )
    assert r.status_code == 201


def test_register_requires_valid_invite_code_when_flag_on(client):
    from settings_store import set_value

    conn = client.app.dependency_overrides[get_conn]()
    set_value(conn, "require_invite_code", "true")

    r = client.post(
        "/auth/register",
        json={
            "email": "noinvite@y.com",
            "email_confirm": "noinvite@y.com",
            "name": "No Invite",
            "password": "password123",
            "password_confirm": "password123",
            "tos_accepted": True,
        },
    )
    assert r.status_code == 422

    r2 = client.post(
        "/auth/register",
        json={
            "email": "badinvite@y.com",
            "email_confirm": "badinvite@y.com",
            "name": "Bad Invite",
            "password": "password123",
            "password_confirm": "password123",
            "tos_accepted": True,
            "invite_code": "BOGU-SCOD",
        },
    )
    assert r2.status_code == 422

    from invite_codes import generate_code

    code = generate_code()
    conn.execute(
        "INSERT INTO invite_codes (code, note, max_uses, created_by_user_id) "
        "VALUES (?, NULL, 1, 1)",
        (code,),
    )
    conn.commit()

    r3 = client.post(
        "/auth/register",
        json={
            "email": "goodinvite@y.com",
            "email_confirm": "goodinvite@y.com",
            "name": "Good Invite",
            "password": "password123",
            "password_confirm": "password123",
            "tos_accepted": True,
            "invite_code": code,
        },
    )
    assert r3.status_code == 201

    row = conn.execute(
        "SELECT uses_count FROM invite_codes WHERE code = ?", (code,)
    ).fetchone()
    assert row["uses_count"] == 1


def test_register_records_consents_and_exposes_them(client):
    r = client.post(
        "/auth/register",
        json={
            "email": "consentflow@y.com",
            "email_confirm": "consentflow@y.com",
            "name": "Consent Flow",
            "password": "password123",
            "password_confirm": "password123",
            "tos_accepted": True,
        },
    )
    assert r.status_code == 201

    consents = client.get("/auth/consents")
    assert consents.status_code == 200
    body = consents.json()
    assert len(body) == 2
    types = {c["document_type"] for c in body}
    assert types == {"terms_of_service", "privacy_policy"}
    for c in body:
        assert c["document_version"]
        assert c["accepted_at"]


def test_login_wrong_password_401(client):
    client.post(
        "/auth/register",
        json={
            "email": "x@y.com",
            "email_confirm": "x@y.com",
            "name": "X",
            "password": "password123",
            "password_confirm": "password123",
            "tos_accepted": True,
        },
    )
    r = client.post("/auth/login", json={"email": "x@y.com", "password": "nope"})
    assert r.status_code == 401


def test_me_without_cookie_401(client):
    assert client.get("/auth/me").status_code == 401


def test_update_display_currency(client):
    register = client.post(
        "/auth/register",
        json={
            "email": "curr@y.com",
            "email_confirm": "curr@y.com",
            "name": "Curr User",
            "password": "password123",
            "password_confirm": "password123",
            "tos_accepted": True,
        },
    )
    assert register.status_code == 201

    resp = client.put("/auth/me/currency", json={"display_currency": "USD"})
    assert resp.status_code == 204

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["display_currency"] == "USD"


def test_put_show_debts_updates_preference():
    # Builds its own conn/app (rather than reusing the shared `client` fixture) and
    # overrides get_current_user directly, so it never calls /auth/register or
    # /auth/login — both rate-limited endpoints whose buckets are shared process-wide
    # across every test file in the same pytest session.
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    user = repo.create_user(
        conn,
        email="debts-toggle@y.com",
        name="Debts Toggle",
        password_hash=hash_password("password123"),
    )
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: repo.get_user_by_id(conn, user["id"])
    app.include_router(router)
    local_client = TestClient(app)

    resp = local_client.put("/auth/me/show-debts", json={"show_debts": True})
    assert resp.status_code == 204


def test_update_name_splits_and_returns_in_me():
    # Same pattern as test_put_show_debts_updates_preference — avoids the
    # rate-limited /auth/register endpoint by creating the user directly.
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    user = repo.create_user(
        conn,
        email="rename-router@y.com",
        name="Old Name",
        password_hash=hash_password("password123"),
    )
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: repo.get_user_by_id(conn, user["id"])
    app.include_router(router)
    local_client = TestClient(app)

    resp = local_client.put("/auth/me/name", json={"first_name": "New", "last_name": "Name"})
    assert resp.status_code == 204

    app.dependency_overrides[get_current_user] = lambda: repo.get_user_by_id(conn, user["id"])
    me = local_client.get("/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["first_name"] == "New"
    assert body["last_name"] == "Name"
    assert body["name"] == "New Name"


def test_login_sets_cookie_domain_when_configured(client, monkeypatch):
    # Smoke test that registration still succeeds and issues a cookie when cookie_domain is
    # set to a foreign domain. NOTE: we can't assert via client.cookies.get() here — httpx's
    # TestClient cookie jar won't store cookies scoped to a domain that doesn't match the
    # "testserver" host it requests against, regardless of correctness (see the precise
    # raw-header assertion in test_login_cookie_domain_attribute_present below).
    from config import settings

    monkeypatch.setattr(settings, "cookie_domain", ".pfh.example.com")
    resp = client.post(
        "/auth/register",
        json={
            "email": "domaincookie@example.com",
            "email_confirm": "domaincookie@example.com",
            "name": "Domain Cookie",
            "password": "Sup3rSecret!",
            "password_confirm": "Sup3rSecret!",
            "tos_accepted": True,
        },
    )
    assert resp.status_code == 201
    assert resp.headers.get("set-cookie") is not None


def test_login_cookie_domain_attribute_present(client, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "cookie_domain", ".pfh.example.com")
    resp = client.post(
        "/auth/register",
        json={
            "email": "domaincookie2@example.com",
            "email_confirm": "domaincookie2@example.com",
            "name": "Domain Cookie2",
            "password": "Sup3rSecret!",
            "password_confirm": "Sup3rSecret!",
            "tos_accepted": True,
        },
    )
    if hasattr(resp.headers, "get_list"):
        raw_cookie_headers = resp.headers.get_list("set-cookie")
    else:
        raw_cookie_headers = [resp.headers.get("set-cookie", "")]
    assert any("Domain=.pfh.example.com" in h for h in raw_cookie_headers)


# ---------------------------------------------------------------------------
# foroba#183 — DELETE /auth/account (GDPR erasure orchestrator)
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _FakeAsyncClient:
    """Stand-in for httpx.AsyncClient — fakes Pazuru/Tsumi's /account/erase
    response so this test never makes a real network call."""

    def __init__(self, *args, status_code: int = 204, raise_error: bool = False, **kwargs):
        self._status_code = status_code
        self._raise_error = raise_error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    seen_cookies: ClassVar[list] = []

    async def delete(self, url, cookies=None):
        type(self).seen_cookies.append(cookies)
        if self._raise_error:
            raise httpx.ConnectError("simulated upstream failure")
        return _FakeResponse(self._status_code)


def _client_with_conn():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    init_settings(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(router)
    return TestClient(app), conn


def _register(client, email="delete-me@y.com", password="password123"):
    r = client.post(
        "/auth/register",
        json={
            "email": email,
            "email_confirm": email,
            "name": "Delete Me",
            "password": password,
            "password_confirm": password,
            "tos_accepted": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_delete_account_wrong_password_401(monkeypatch):
    client, conn = _client_with_conn()
    _register(client, email="wrongpw@y.com")
    monkeypatch.setattr(
        "auth.router.httpx.AsyncClient", lambda *a, **kw: _FakeAsyncClient(status_code=204)
    )
    r = client.request("DELETE", "/auth/account", json={"password": "not-the-password"})
    assert r.status_code == 401
    row = conn.execute("SELECT count(*) FROM users WHERE email = ?", ("wrongpw@y.com",)).fetchone()
    assert row[0] == 1


def test_delete_account_success_204_clears_cookie_and_removes_user(monkeypatch):
    client, conn = _client_with_conn()
    _register(client, email="gone@y.com")
    monkeypatch.setattr(
        "auth.router.httpx.AsyncClient", lambda *a, **kw: _FakeAsyncClient(status_code=204)
    )
    r = client.request("DELETE", "/auth/account", json={"password": "password123"})
    assert r.status_code == 204, r.text
    raw = (
        r.headers.get_list("set-cookie")
        if hasattr(r.headers, "get_list")
        else [r.headers.get("set-cookie", "")]
    )
    assert any("suite_session=" in h and "Max-Age=0" in h for h in raw)
    assert conn.execute("SELECT count(*) FROM users WHERE email = ?", ("gone@y.com",)).fetchone()[
        0
    ] == 0


def test_delete_account_upstream_failure_502_leaves_user_row_untouched(monkeypatch):
    client, conn = _client_with_conn()
    _register(client, email="stay@y.com")
    monkeypatch.setattr(
        "auth.router.httpx.AsyncClient", lambda *a, **kw: _FakeAsyncClient(status_code=500)
    )
    r = client.request("DELETE", "/auth/account", json={"password": "password123"})
    assert r.status_code == 502
    assert conn.execute("SELECT count(*) FROM users WHERE email = ?", ("stay@y.com",)).fetchone()[
        0
    ] == 1


def test_delete_account_upstream_connection_error_502(monkeypatch):
    client, conn = _client_with_conn()
    _register(client, email="staytoo@y.com")
    monkeypatch.setattr(
        "auth.router.httpx.AsyncClient", lambda *a, **kw: _FakeAsyncClient(raise_error=True)
    )
    r = client.request("DELETE", "/auth/account", json={"password": "password123"})
    assert r.status_code == 502
    assert conn.execute(
        "SELECT count(*) FROM users WHERE email = ?", ("staytoo@y.com",)
    ).fetchone()[0] == 1


def _add_subscription(conn, user_id: int, sub_id: str, status: str) -> None:
    conn.execute(
        "INSERT INTO subscriptions (user_id, provider, provider_subscription_id, status, "
        "last_event_at, updated_at) VALUES (?, 'paddle', ?, ?, '2026-10-01T00:00:00Z', "
        "'2026-10-01T00:00:00Z')",
        (user_id, sub_id, status),
    )
    conn.commit()


class _RecordingProvider:
    def __init__(self, fail: bool = False):
        self.cancelled: list[str] = []
        self.fail = fail

    def cancel_subscription(self, subscription_id: str) -> None:
        from billing.provider import BillingProviderError

        if self.fail:
            raise BillingProviderError("boom")
        self.cancelled.append(subscription_id)


def test_delete_account_cancels_live_subscriptions_first(monkeypatch):
    client, conn = _client_with_conn()
    user = _register(client, email="payer@y.com")
    uid = conn.execute("SELECT id FROM users WHERE email = ?", ("payer@y.com",)).fetchone()[0]
    _add_subscription(conn, uid, "sub_live", "active")
    _add_subscription(conn, uid, "sub_old", "canceled")
    prov = _RecordingProvider()
    monkeypatch.setattr("auth.router.get_provider", lambda name: prov)
    monkeypatch.setattr(
        "auth.router.httpx.AsyncClient", lambda *a, **kw: _FakeAsyncClient(status_code=204)
    )
    r = client.request("DELETE", "/auth/account", json={"password": "password123"})
    assert r.status_code == 204, r.text
    assert prov.cancelled == ["sub_live"]
    assert user is not None


def test_delete_account_cancel_failure_502_and_nothing_erased(monkeypatch):
    client, conn = _client_with_conn()
    _register(client, email="payer2@y.com")
    uid = conn.execute("SELECT id FROM users WHERE email = ?", ("payer2@y.com",)).fetchone()[0]
    _add_subscription(conn, uid, "sub_live", "trialing")
    monkeypatch.setattr("auth.router.get_provider", lambda name: _RecordingProvider(fail=True))

    def _must_not_call(*a, **kw):
        raise AssertionError("erasure must not start when cancellation failed")

    monkeypatch.setattr("auth.router.httpx.AsyncClient", _must_not_call)
    r = client.request("DELETE", "/auth/account", json={"password": "password123"})
    assert r.status_code == 502
    assert "subscription" in r.json()["detail"].lower()
    assert conn.execute("SELECT count(*) FROM users WHERE id = ?", (uid,)).fetchone()[0] == 1


def test_delete_account_bearer_only_client_forwards_session_to_apps(monkeypatch):
    """Mobile clients authenticate with a Bearer JWT and hold no suite_session cookie;
    Pazuru/Tsumi's require_auth still needs a session, so Foroba must forward the one
    it resolved (else both answer 401 and deletion fails with a 502)."""
    client, _conn = _client_with_conn()
    _register(client, email="bearer@y.com")
    token = client.cookies.get("suite_session")
    assert token
    client.cookies.clear()
    _FakeAsyncClient.seen_cookies = []
    monkeypatch.setattr(
        "auth.router.httpx.AsyncClient", lambda *a, **kw: _FakeAsyncClient(status_code=204)
    )
    r = client.request(
        "DELETE",
        "/auth/account",
        json={"password": "password123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204, r.text
    assert len(_FakeAsyncClient.seen_cookies) == 2
    for sent in _FakeAsyncClient.seen_cookies:
        assert sent["suite_session"] == token
