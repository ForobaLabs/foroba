import pytest
from conftest import GATEWAY_TOKEN
from fastapi import FastAPI
from fastapi.testclient import TestClient

import consent
import db
import prefs
from auth import Caller

app = FastAPI()
app.include_router(prefs.router)
client = TestClient(app)
U7 = Caller(user_id=7, tier="free", is_admin=False)


@pytest.fixture(autouse=True)
def cloud_on(monkeypatch):
    monkeypatch.setenv("AI_CLOUD_ENABLED", "true")


def test_resolve_default_local_no_notice():
    r = prefs.resolve(db.connect(), U7, "pazuru", "chat")
    assert (r.mode, r.byok_provider, r.notice) == ("local", None, None)


def test_feature_overrides_app_default():
    conn = db.connect()
    consent.record(conn, 7, "cloudflare", "accept", None)
    prefs.put(conn, 7, "pazuru", "*", "cloud", None)
    prefs.put(conn, 7, "pazuru", "csv_import", "local", None)
    assert prefs.resolve(conn, U7, "pazuru", "csv_import").mode == "local"
    assert prefs.resolve(conn, U7, "pazuru", "chat").mode == "cloud"


def test_app_default_applies_when_no_feature_row():
    conn = db.connect()
    consent.record(conn, 7, "cloudflare", "accept", None)
    prefs.put(conn, 7, "tsumi", "*", "cloud", None)
    assert prefs.resolve(conn, U7, "tsumi", "jeli").mode == "cloud"


def test_cloud_without_consent_resolves_local_consent_required():
    conn = db.connect()
    prefs.put(conn, 7, "pazuru", "chat", "cloud", None)
    r = prefs.resolve(conn, U7, "pazuru", "chat")
    assert (r.mode, r.notice) == ("local", "consent_required")


def test_withdrawn_consent_blocks_next_request():
    conn = db.connect()
    prefs.put(conn, 7, "pazuru", "chat", "cloud", None)
    consent.record(conn, 7, "cloudflare", "accept", None)
    assert prefs.resolve(conn, U7, "pazuru", "chat").mode == "cloud"
    consent.record(conn, 7, "cloudflare", "withdraw", None)
    r = prefs.resolve(conn, U7, "pazuru", "chat")
    assert (r.mode, r.notice) == ("local", "consent_required")


def test_byok_without_key_resolves_local_key_invalid():
    conn = db.connect()
    consent.record(conn, 7, "byok:openai", "accept", None)
    prefs.put(conn, 7, "pazuru", "chat", "byok", "openai")
    r = prefs.resolve(conn, U7, "pazuru", "chat")
    assert (r.mode, r.notice) == ("local", "byok_key_invalid")


def test_byok_with_key_and_consent_resolves_byok():
    conn = db.connect()
    consent.record(conn, 7, "byok:openai", "accept", None)
    conn.execute(
        "INSERT INTO byok_keys(user_id, provider, secret_enc, last4, status, created_at) "
        "VALUES (7, 'openai', x'00', 'abcd', 'ok', '2026-10-30T00:00:00Z')"
    )
    conn.commit()
    prefs.put(conn, 7, "pazuru", "chat", "byok", "openai")
    r = prefs.resolve(conn, U7, "pazuru", "chat")
    assert (r.mode, r.byok_provider, r.notice) == ("byok", "openai", None)


def test_cloud_disabled_flag_resolves_local_unless_allowlisted(monkeypatch):
    import config

    monkeypatch.setenv("AI_CLOUD_ENABLED", "false")
    config.get_settings.cache_clear()
    conn = db.connect()
    consent.record(conn, 7, "cloudflare", "accept", None)
    prefs.put(conn, 7, "pazuru", "chat", "cloud", None)
    r = prefs.resolve(conn, U7, "pazuru", "chat")
    assert (r.mode, r.notice) == ("local", "cloud_unavailable")
    monkeypatch.setenv("AI_TEST_ALLOWLIST", "7")
    config.get_settings.cache_clear()
    assert prefs.resolve(conn, U7, "pazuru", "chat").mode == "cloud"


def _h(make_token, user):
    return {
        "X-AI-Gateway-Token": GATEWAY_TOKEN,
        "Authorization": f"Bearer {make_token(sub=str(user))}",
    }


def test_unknown_feature_put_422(make_token):
    body = {"app": "pazuru", "feature": "nope", "provider": "cloud"}
    assert (
        client.put("/v1/prefs", json=body, headers=_h(make_token, 7)).status_code == 422
    )
    body = {"app": "nope", "feature": "*", "provider": "cloud"}
    assert (
        client.put("/v1/prefs", json=body, headers=_h(make_token, 7)).status_code == 422
    )


def test_put_cloud_without_consent_is_stored(make_token):
    body = {"app": "pazuru", "feature": "chat", "provider": "cloud"}
    r = client.put("/v1/prefs", json=body, headers=_h(make_token, 7))
    assert r.status_code == 200
    assert r.json() == {
        "app": "pazuru",
        "feature": "chat",
        "provider": "cloud",
        "byok_provider": None,
    }


def test_byok_pref_needs_known_byok_provider(make_token):
    h = _h(make_token, 7)
    base = {"app": "pazuru", "feature": "chat", "provider": "byok"}
    assert client.put("/v1/prefs", json=base, headers=h).status_code == 422
    assert (
        client.put(
            "/v1/prefs", json={**base, "byok_provider": "evil"}, headers=h
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/v1/prefs", json={**base, "byok_provider": "openai"}, headers=h
        ).status_code
        == 200
    )


def test_prefs_isolated_per_user(make_token):
    body = {"app": "pazuru", "feature": "chat", "provider": "cloud"}
    client.put("/v1/prefs", json=body, headers=_h(make_token, 7))
    assert len(client.get("/v1/prefs", headers=_h(make_token, 7)).json()) == 1
    assert client.get("/v1/prefs", headers=_h(make_token, 8)).json() == []
