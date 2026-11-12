"""Waitlist (Plan D, S1): table, service, public routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import db
import waitlist_service as ws
from auth.conn import get_conn
from config import settings
from main import app
from rate_limit import limiter


def _memory_conn():
    return db.connect(":memory:")


def test_waitlist_table_exists_with_expected_columns():
    conn = _memory_conn()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(waitlist)")}
    assert cols == {
        "id", "email", "apps", "lang", "consent_at",
        "confirm_token_hash", "confirmed_at", "created_at",
    }


def test_join_returns_token_and_stores_only_its_hash():
    conn = _memory_conn()
    token = ws.join(
        conn, email="  Ada@Example.org ", apps=["naforo", "kelen"], lang="it", consent=True
    )
    assert token and len(token) >= 32
    row = conn.execute(
        "SELECT email, apps, lang, confirm_token_hash, confirmed_at FROM waitlist"
    ).fetchone()
    assert row[0] == "ada@example.org"
    assert row[1] == "kelen,naforo"
    assert row[2] == "it"
    assert row[3] != token and len(row[3]) == 64
    assert row[4] is None


@pytest.mark.parametrize(
    "kwargs, code",
    [
        ({"email": "not-an-email"}, "invalid_email"),
        ({"email": "a@b.c" + "x" * 300}, "invalid_email"),
        ({"apps": ["pazuru"]}, "invalid_apps"),
        ({"consent": False}, "consent_required"),
    ],
)
def test_join_rejects_bad_input(kwargs, code):
    conn = _memory_conn()
    args = {"email": "a@example.org", "apps": ["naforo"], "lang": "en", "consent": True, **kwargs}
    with pytest.raises(ws.WaitlistError, match=code):
        ws.join(conn, **args)


def test_unknown_lang_falls_back_to_en():
    conn = _memory_conn()
    ws.join(conn, email="a@example.org", apps=[], lang="de", consent=True)
    assert conn.execute("SELECT lang FROM waitlist").fetchone()[0] == "en"


def test_rejoin_unconfirmed_rotates_token():
    conn = _memory_conn()
    first = ws.join(conn, email="a@example.org", apps=["naforo"], lang="en", consent=True)
    second = ws.join(conn, email="a@example.org", apps=["yiriba"], lang="fr", consent=True)
    assert first != second
    assert ws.confirm(conn, first) is False
    assert ws.confirm(conn, second) is True
    assert conn.execute("SELECT COUNT(*) FROM waitlist").fetchone()[0] == 1


def test_confirm_is_single_use_and_rejoin_after_confirm_returns_none():
    conn = _memory_conn()
    token = ws.join(conn, email="a@example.org", apps=[], lang="en", consent=True)
    assert ws.confirm(conn, token) is True
    assert ws.confirm(conn, token) is False
    assert ws.join(conn, email="a@example.org", apps=[], lang="en", consent=True) is None


def test_confirm_unknown_token():
    assert ws.confirm(_memory_conn(), "nope") is False


@pytest.fixture
def client(monkeypatch):
    conn = _memory_conn()
    sent: list[tuple[str, str, str]] = []
    import waitlist_router

    monkeypatch.setattr(waitlist_router, "send_email", lambda to, s, b: sent.append((to, s, b)))
    monkeypatch.setattr(settings, "site_base_url", "")
    monkeypatch.setattr(settings, "api_public_base_url", "https://api.example")
    app.dependency_overrides[get_conn] = lambda: conn
    limiter.reset()
    try:
        yield TestClient(app), conn, sent
    finally:
        app.dependency_overrides.pop(get_conn, None)
        limiter.reset()


def _body(**kw):
    return {"email": "a@example.org", "apps": ["naforo"], "lang": "en", "consent": True, **kw}


def test_post_waitlist_sends_confirm_link(client):
    c, _, sent = client
    r = c.post("/api/public/v1/waitlist", json=_body())
    assert r.status_code == 202 and r.json() == {"status": "pending"}
    assert len(sent) == 1 and sent[0][0] == "a@example.org"
    assert "/api/public/v1/waitlist/confirm?token=" in sent[0][2]


def test_post_waitlist_already_confirmed_is_indistinguishable(client):
    c, _, sent = client
    c.post("/api/public/v1/waitlist", json=_body())
    token = sent[0][2].split("token=")[1].split()[0]
    assert c.get(f"/api/public/v1/waitlist/confirm?token={token}").json() == {"confirmed": True}
    r = c.post("/api/public/v1/waitlist", json=_body())
    assert r.status_code == 202 and r.json() == {"status": "pending"}
    assert len(sent) == 1  # no second email


def test_post_waitlist_validation_error(client):
    c, _, sent = client
    r = c.post("/api/public/v1/waitlist", json=_body(consent=False))
    assert r.status_code == 422 and r.json() == {"detail": "consent_required"}
    assert sent == []


def test_confirm_redirects_to_site_when_configured(client, monkeypatch):
    c, _, sent = client
    monkeypatch.setattr(settings, "site_base_url", "https://site.example")
    c.post("/api/public/v1/waitlist", json=_body(lang="it"))
    token = sent[0][2].split("token=")[1].split()[0]
    r = c.get(f"/api/public/v1/waitlist/confirm?token={token}", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "https://site.example/it/contact.html?waitlist=confirmed"
    r = c.get("/api/public/v1/waitlist/confirm?token=bad", follow_redirects=False)
    assert r.headers["location"] == "https://site.example/en/contact.html?waitlist=invalid"


def test_post_waitlist_rate_limited(client):
    c, _, _ = client
    codes = [
        c.post("/api/public/v1/waitlist", json=_body(email=f"u{i}@example.org")).status_code
        for i in range(6)
    ]
    assert codes[:5] == [202] * 5 and codes[5] == 429


def test_confirm_link_ignores_host_header(client, monkeypatch):
    """Plan AU M-4: the e-mailed link comes from API_PUBLIC_BASE_URL, never the Host header."""
    c, _, sent = client
    monkeypatch.setattr(settings, "api_public_base_url", "https://legacy.example.org/")
    c.post("/api/public/v1/waitlist", json=_body(), headers={"Host": "evil.example"})
    assert "evil.example" not in sent[0][2]
    assert "https://legacy.example.org/api/public/v1/waitlist/confirm?token=" in sent[0][2]


def test_no_email_when_base_url_unset(client, monkeypatch):
    c, _, sent = client
    monkeypatch.setattr(settings, "api_public_base_url", "")
    r = c.post("/api/public/v1/waitlist", json=_body(email="b@example.org"))
    assert r.status_code == 202 and r.json() == {"status": "pending"}
    assert sent == []
