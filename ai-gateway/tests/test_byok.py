import json
import logging

import httpx
import pytest
import respx
from cryptography.fernet import Fernet

import consent
import db
import prefs

OPENAI = "https://api.openai.com/v1/chat/completions"
KEY = "sk-live-ABCDEFGH1234567890WXYZ"


def ok_reply(text="pong"):
    return httpx.Response(
        200, json={"model": "gpt-4o-mini", "choices": [{"message": {"content": text}}]}
    )


def put_key(api, user=7, key=KEY, provider="openai", model="gpt-4o-mini", **extra):
    return api(
        "PUT", "/v1/byok", user=user,
        json={"provider": provider, "api_key": key, "model": model, **extra},
    )


@respx.mock
def test_save_never_returns_key(api):
    respx.post(OPENAI).mock(return_value=ok_reply())
    res = put_key(api)
    assert res.status_code == 200
    body = res.text
    assert not any(KEY[i : i + 8] in body for i in range(len(KEY) - 7))
    assert res.json()["last4"] == KEY[-4:] and res.json()["status"] == "ok"


@respx.mock
def test_stored_secret_is_encrypted(api):
    from config import get_settings

    respx.post(OPENAI).mock(return_value=ok_reply())
    put_key(api)
    row = db.connect().execute("SELECT secret_enc FROM byok_keys WHERE user_id=7").fetchone()
    raw = bytes(row["secret_enc"])
    assert KEY.encode() not in raw
    assert Fernet(get_settings().field_key).decrypt(raw).decode() == KEY


@respx.mock
def test_save_sends_one_token_test_call_with_user_key(api):
    route = respx.post(OPENAI).mock(return_value=ok_reply())
    put_key(api)
    req = route.calls[0].request
    assert req.headers["authorization"] == f"Bearer {KEY}"
    assert json.loads(req.content)["max_tokens"] == 1


@respx.mock
def test_list_shows_last4_only(api):
    respx.post(OPENAI).mock(return_value=ok_reply())
    put_key(api)
    res = api("GET", "/v1/byok")
    assert res.status_code == 200
    item = res.json()[0]
    assert set(item) == {"provider", "last4", "model", "status", "created_at"}
    assert item["last4"] == KEY[-4:]
    assert KEY[:12] not in res.text


@respx.mock
def test_failed_test_call_not_stored(api):
    respx.post(OPENAI).mock(return_value=httpx.Response(401))
    res = put_key(api)
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "byok_test_failed"
    assert KEY not in res.text
    assert api("GET", "/v1/byok").json() == []


@pytest.mark.parametrize(
    "over", [{"provider": "nope"}, {"model": "gpt-9000"}, {"provider": "cloudflare"}]
)
def test_unknown_provider_or_model_422(api, over):
    res = put_key(api, **over) if "provider" not in over else api(
        "PUT", "/v1/byok",
        json={"provider": over["provider"], "api_key": KEY, "model": "gpt-4o-mini"},
    )
    assert res.status_code == 422
    assert KEY not in res.text


def test_validation_error_never_echoes_key(api):
    res = api("PUT", "/v1/byok", json={"provider": "openai", "api_key": KEY})
    assert res.status_code == 422
    assert KEY not in res.text and "input" not in res.text


@respx.mock
def test_byok_401_falls_back_and_never_leaks_key(api, caplog, monkeypatch):
    monkeypatch.setenv("AI_CLOUD_ENABLED", "true")
    respx.post(OPENAI).mock(return_value=ok_reply())
    put_key(api)
    conn = db.connect()
    consent.record(conn, 7, "byok:openai", "accept", None)
    prefs.put(conn, 7, "pazuru", "chat", "byok", "openai")
    respx.post(OPENAI).mock(return_value=httpx.Response(401, text=f"bad key {KEY}"))
    with caplog.at_level(logging.DEBUG):
        res = api(
            "POST", "/v1/chat",
            json={"app": "pazuru", "feature": "chat", "task": "chat",
                  "messages": [{"role": "user", "content": "ciao"}]},
        )
    body = res.json()
    assert body["route"] == "local" and body["meta"]["notice"] == "byok_key_invalid"
    assert KEY not in res.text and KEY not in caplog.text
    assert api("GET", "/v1/byok").json()[0]["status"] == "invalid"


@respx.mock
def test_delete_key_resets_prefs_to_local(api):
    respx.post(OPENAI).mock(return_value=ok_reply())
    put_key(api)
    conn = db.connect()
    prefs.put(conn, 7, "pazuru", "chat", "byok", "openai")
    prefs.put(conn, 7, "pazuru", "lab", "cloud", None)
    assert api("DELETE", "/v1/byok/openai").status_code == 204
    assert api("GET", "/v1/byok").json() == []
    got = {(p.feature): (p.provider, p.byok_provider) for p in prefs.get_all(db.connect(), 7)}
    assert got["chat"] == ("local", None) and got["lab"] == ("cloud", None)


@respx.mock
def test_user_cannot_read_other_users_keys(api):
    respx.post(OPENAI).mock(return_value=ok_reply())
    put_key(api, user=7)
    assert api("GET", "/v1/byok", user=8).json() == []
    assert api("DELETE", "/v1/byok/openai", user=8).status_code == 204
    assert len(api("GET", "/v1/byok", user=7).json()) == 1


@respx.mock
def test_test_endpoint_reports_status(api):
    respx.post(OPENAI).mock(return_value=ok_reply())
    put_key(api)
    assert api("POST", "/v1/byok/openai/test").json() == {"ok": True, "status": "ok"}
    respx.post(OPENAI).mock(return_value=httpx.Response(401))
    assert api("POST", "/v1/byok/openai/test").json() == {"ok": False, "status": "invalid"}
    assert api("GET", "/v1/byok").json()[0]["status"] == "invalid"
    respx.post(OPENAI).mock(return_value=ok_reply())
    assert api("POST", "/v1/byok/openai/test").json() == {"ok": True, "status": "ok"}
    assert api("POST", "/v1/byok/mistral/test").status_code == 404


@respx.mock
def test_cloudflare_byok_needs_account_id(api):
    cf = "https://api.cloudflare.com/client/v4/accounts/acc9/ai/v1/chat/completions"
    model = "@cf/meta/llama-4-scout-17b-16e-instruct"
    assert put_key(api, provider="cloudflare", model=model).status_code == 422
    route = respx.post(cf).mock(return_value=ok_reply())
    res = put_key(api, provider="cloudflare", model=model, account_id="acc9")
    assert res.status_code == 200 and route.called
    assert "acc9" not in res.text
    row = db.connect().execute("SELECT account_id_enc FROM byok_keys WHERE user_id=7").fetchone()
    assert b"acc9" not in bytes(row["account_id_enc"])
