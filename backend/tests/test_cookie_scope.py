"""Host-conditional cookie domain (free-tier infra plan, Task 1).

`COOKIE_DOMAIN` only applies to requests whose Host is under that domain; every other host
(DuckDNS during the transition, localhost, look-alikes) keeps host-only cookies.
"""

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.conn import get_conn
from auth.router import router as auth_router
from cookie_scope import cookie_domain_for
from db import init_schema, seed_mock_users
from rate_limit import limiter
from settings_store import init_settings
from stepup_router import router as stepup_router
from twofa.router import router as twofa_router

DOMAIN = ".forobalabs.com"
NEW_HOST = "https://app.forobalabs.com"
OLD_HOST = "https://foroba-app.duckdns.org"


@pytest.mark.parametrize(
    "host,expected",
    [
        ("app.forobalabs.com", DOMAIN),
        ("APP.ForobaLabs.com", DOMAIN),
        ("app.forobalabs.com:443", DOMAIN),
        ("forobalabs.com", DOMAIN),
        ("foroba-app.duckdns.org", None),
        ("evilforobalabs.com", None),
        ("forobalabs.com.attacker.net", None),
        ("localhost", None),
        (None, None),
        ("", None),
    ],
)
def test_cookie_domain_for(monkeypatch, host, expected):
    from config import settings

    monkeypatch.setattr(settings, "cookie_domain", DOMAIN)
    assert cookie_domain_for(host) == expected


def test_cookie_domain_unset_is_host_only(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "cookie_domain", "")
    assert cookie_domain_for("app.forobalabs.com") is None


@pytest.fixture(autouse=True)
def _scope(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "cookie_domain", DOMAIN)
    limiter.reset()
    yield
    limiter.reset()


def _app():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    init_settings(conn)
    seed_mock_users(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(auth_router)
    app.include_router(twofa_router)
    app.include_router(stepup_router)
    return app, conn


def _cookies(resp):
    return resp.headers.get_list("set-cookie")


def _register(client, email="scope@example.com"):
    r = client.post(
        "/auth/register",
        json={
            "email": email,
            "email_confirm": email,
            "name": "Scope",
            "password": "Sup3rSecret!",
            "password_confirm": "Sup3rSecret!",
            "tos_accepted": True,
        },
    )
    assert r.status_code == 201, r.text
    return r


def test_register_sets_domain_cookie_on_forobalabs_host():
    app, _ = _app()
    r = _register(TestClient(app, base_url=NEW_HOST))
    assert any("suite_session=" in h and f"Domain={DOMAIN}" in h for h in _cookies(r))


def test_register_host_only_on_duckdns_host():
    app, _ = _app()
    r = _register(TestClient(app, base_url=OLD_HOST))
    session = [h for h in _cookies(r) if "suite_session=" in h]
    assert session and not any("Domain=" in h for h in session)


def test_logout_clears_both_variants():
    app, _ = _app()
    client = TestClient(app, base_url=NEW_HOST)
    _register(client)
    r = client.post("/auth/logout")
    assert r.status_code == 204
    dead = [h for h in _cookies(r) if "suite_session=" in h and "Max-Age=0" in h]
    assert any(f"Domain={DOMAIN}" in h for h in dead)
    assert any("Domain=" not in h for h in dead)


def test_logout_on_duckdns_host_clears_host_only_only():
    app, _ = _app()
    client = TestClient(app, base_url=OLD_HOST)
    _register(client)
    r = client.post("/auth/logout")
    dead = [h for h in _cookies(r) if "suite_session=" in h and "Max-Age=0" in h]
    assert dead and not any("Domain=" in h for h in dead)


def test_account_delete_clears_both_variants(monkeypatch):
    class _Resp:
        status_code = 204

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def delete(self, *a, **kw):
            return _Resp()

        async def request(self, *a, **kw):
            return _Resp()

        async def post(self, *a, **kw):
            return _Resp()

    monkeypatch.setattr("auth.router.httpx.AsyncClient", _Client)
    app, _ = _app()
    client = TestClient(app, base_url=NEW_HOST)
    _register(client, "gone-scope@example.com")
    r = client.request("DELETE", "/auth/account", json={"password": "Sup3rSecret!"})
    assert r.status_code == 204, r.text
    dead = [h for h in _cookies(r) if "suite_session=" in h and "Max-Age=0" in h]
    assert any(f"Domain={DOMAIN}" in h for h in dead)
    assert any("Domain=" not in h for h in dead)


def test_stepup_cookie_domain_on_forobalabs_host():
    import pyotp

    app, _ = _app()
    client = TestClient(app, base_url=NEW_HOST)
    _register(client, "stepup-scope@example.com")
    secret = client.post("/auth/2fa/enroll").json()["secret"]
    client.post("/auth/2fa/verify", json={"code": pyotp.TOTP(secret).now()})
    r = client.post(
        "/auth/stepup/verify",
        json={"app": "pazuru", "method": "totp", "code": pyotp.TOTP(secret).now()},
    )
    assert r.status_code == 200, r.text
    assert any("stepup_pazuru=" in h and f"Domain={DOMAIN}" in h for h in _cookies(r))
