"""SSRF guard for user-supplied outbound URLs (pre-beta Task 2.4)."""

from __future__ import annotations

import socket

import pytest
from fastapi.testclient import TestClient

import db
import webhook_dispatch_job as wdj
from auth.conn import get_conn
from auth.dependencies import get_current_user
from main import app
from url_guard import UnsafeUrlError, assert_public_https_url

_USER = {
    "id": 1,
    "email": "u@test.local",
    "tier": "premium",
    "audience": "base",
    "is_admin": 0,
    "household_id": None,
}


def _fake_dns(mapping):
    def _gai(host, port, *a, **k):
        ip = mapping.get(host)
        if ip is None:
            raise socket.gaierror("nodename nor servname")
        fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
        return [(fam, socket.SOCK_STREAM, 6, "", (ip, port or 443))]

    return _gai


@pytest.mark.parametrize(
    "url",
    [
        "https://169.254.169.254/latest/meta-data/",
        "https://127.0.0.1/hook",
        "https://localhost/hook",
        "https://LOCALHOST./hook",
        "https://10.0.0.5/hook",
        "https://192.168.1.10/hook",
        "https://172.16.0.1/hook",
        "https://[::1]/hook",
        "https://[fd00::1]/hook",
        "https://[::ffff:127.0.0.1]/hook",
        "https://0.0.0.0/hook",
        "https://2130706433/hook",
        "https://0x7f000001/hook",
        "https://user:pw@example.com/hook",
        "https://printer.local/hook",
        "https://db.internal/hook",
        "https://pazuru/hook",
        "http://example.com/hook",
        "ftp://example.com/hook",
    ],
)
def test_literal_and_internal_urls_rejected(url, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns({"example.com": "93.184.216.34"}))
    with pytest.raises(UnsafeUrlError):
        assert_public_https_url(url)


def test_hostname_resolving_to_private_ip_rejected(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns({"evil.example.com": "10.1.2.3"}))
    with pytest.raises(UnsafeUrlError):
        assert_public_https_url("https://evil.example.com/hook", resolve=True)


def test_public_url_accepted(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns({"hooks.example.com": "93.184.216.34"}))
    assert (
        assert_public_https_url("https://hooks.example.com/h?x=1", resolve=True)
        == "https://hooks.example.com/h?x=1"
    )


def test_unresolvable_host_ok_at_creation_rejected_at_dispatch(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns({}))
    assert_public_https_url("https://later.example.com/h")  # creation: syntax only
    with pytest.raises(UnsafeUrlError):
        assert_public_https_url("https://later.example.com/h", resolve=True)


def test_create_webhook_route_rejects_metadata_ip():
    conn = db.connect(":memory:")
    app.dependency_overrides[get_current_user] = lambda: _USER
    app.dependency_overrides[get_conn] = lambda: conn
    try:
        resp = TestClient(app).post(
            "/auth/webhooks", json={"target_url": "https://169.254.169.254/latest"}
        )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_conn, None)


class _MustNotPost:
    called = False

    async def post(self, *a, **k):
        _MustNotPost.called = True
        raise AssertionError("must not POST to a private target")


@pytest.mark.asyncio
async def test_dispatch_refuses_target_that_now_resolves_to_private_ip(monkeypatch):
    """DNS rebinding: a hostname valid at creation must be re-checked at delivery."""
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns({"rebind.example.com": "127.0.0.1"}))
    conn = db.connect(":memory:")
    row = db.create_webhook(
        conn, user_id=1, target_url="https://rebind.example.com/h", signing_secret="s"
    )
    webhook = dict(row)
    event = {"event_key": "k1", "event": "x", "data": {}}
    _MustNotPost.called = False
    await wdj._deliver_event(_MustNotPost(), conn, webhook, event)
    assert _MustNotPost.called is False
