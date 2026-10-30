import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

import consent
import db
import prefs
import quota
import usage
from masking import engine

CF_URL = "https://api.cloudflare.com/client/v4/accounts/acc1/ai/v1/chat/completions"
GEM_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
CORPUS = Path(__file__).parent / "fixtures" / "masking_corpus"
IBAN = "IT60X0542811101000000123456"
PROMPT = f"Il mio IBAN è {IBAN}, scrivimi a paolo.verdi@example.com"


@pytest.fixture(autouse=True)
def cloud_env(monkeypatch):
    for k, v in {
        "AI_CLOUD_ENABLED": "true",
        "CF_ACCOUNT_ID": "acc1",
        "CF_API_TOKEN": "cf-SECRET-token",
        "AI_TEST_ALLOWLIST": "",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(usage, "now", lambda: NOW)


def enable(user=7, app="pazuru", feature="chat", provider="cloud"):
    conn = db.connect()
    consent.record(conn, user, "cloudflare", "accept", None)
    prefs.put(conn, user, app, feature, provider, None)
    conn.close()


def body(content=PROMPT, **over):
    base = {
        "app": "pazuru",
        "feature": "chat",
        "task": "chat",
        "messages": [{"role": "user", "content": content}],
    }
    base.update(over)
    return base


def ok(content="ciao", neurons=11):
    return httpx.Response(
        200,
        json={
            "model": "@cf/meta/llama-4-scout-17b-16e-instruct",
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {"neurons": neurons},
        },
    )


def sse(*frames, usage_neurons=None):
    out = ""
    for f in frames:
        out += "data: " + json.dumps({"choices": [{"delta": {"content": f}}]}) + "\n\n"
    if usage_neurons is not None:
        out += "data: " + json.dumps({"choices": [], "usage": {"neurons": usage_neurons}}) + "\n\n"
    return out + "data: [DONE]\n\n"


def frames(text):
    out = []
    for block in text.strip().split("\n\n"):
        ev, data = block.split("\n", 1)
        out.append((ev.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


def sent_text(route):
    return json.dumps(json.loads(route.calls[0].request.content), ensure_ascii=False)


@respx.mock
def test_chat_reply_unmasked_and_masked_count_reported(api):
    enable()

    def echo(request):
        msg = json.loads(request.content)["messages"][0]["content"]
        placeholder = msg.split("IBAN è ")[1].split(",")[0]
        return ok(f"Ho letto {placeholder}.")

    respx.post(CF_URL).mock(side_effect=echo)
    res = api("POST", "/v1/chat", json=body()).json()
    assert res["route"] == "remote"
    assert res["text"] == f"Ho letto {IBAN}."
    assert res["meta"]["masked_count"] >= 2 and res["meta"]["notice"] is None
    assert res["meta"]["provider"] == "cloudflare" and res["meta"]["neurons"] == 11


@respx.mock
@pytest.mark.parametrize("name", ["chat_01", "chat_02"])
def test_provider_receives_no_raw_pii(api, name):
    enable()
    route = respx.post(CF_URL).mock(return_value=ok())
    text = (CORPUS / f"{name}.txt").read_text()
    exp = json.loads((CORPUS / f"{name}.expected.json").read_text())
    res = api("POST", "/v1/chat", json=body(text, known_entities=exp["known"]))
    assert res.json()["route"] == "remote"
    sent = sent_text(route)
    assert exp["must_mask"] and not [m for m in exp["must_mask"] if m in sent]


@respx.mock
def test_pref_local_never_calls_provider(api):
    route = respx.post(CF_URL).mock(return_value=ok())
    res = api("POST", "/v1/chat", json=body()).json()
    assert res == {"route": "local", "meta": {"notice": None}}
    assert not route.called


@respx.mock
def test_free_user_over_allowance_routes_local_with_notice(api):
    enable()
    conn = db.connect()
    from auth import Caller

    usage.record(conn, Caller(7, "free", False), "pazuru", "chat", "chat", "cloudflare",
                 "m", 20000, 5, "ok", at="2026-10-02T10:00:00+00:00")
    route = respx.post(CF_URL).mock(return_value=ok())
    res = api("POST", "/v1/chat", json=body()).json()
    assert res["route"] == "local" and res["meta"]["notice"] == "plan_quota_exhausted"
    assert not route.called


@respx.mock
def test_masking_error_routes_local_cloud_unavailable_no_provider_call(api, monkeypatch):
    enable()
    route = respx.post(CF_URL).mock(return_value=ok())

    def boom(*a, **k):
        raise engine.MaskingError("x")

    monkeypatch.setattr(engine, "mask_messages", boom)
    res = api("POST", "/v1/chat", json=body()).json()
    assert res["route"] == "local" and res["meta"]["notice"] == "cloud_unavailable"
    assert not route.called


@respx.mock
def test_breaker_opens_on_4006_until_midnight_utc(api):
    enable()
    route = respx.post(CF_URL).mock(
        return_value=httpx.Response(400, json={"errors": [{"code": 4006}]})
    )
    first = api("POST", "/v1/chat", json=body()).json()
    assert first["route"] == "local" and first["meta"]["notice"] == "cloud_unavailable"
    assert quota._breaker_until == datetime(2026, 10, 16, 0, 0, tzinfo=UTC)
    api("POST", "/v1/chat", json=body())
    assert route.call_count == 1


@respx.mock
def test_rate_limit_11th_request_in_minute_over_http(api):
    enable()
    respx.post(CF_URL).mock(return_value=ok(neurons=1))
    routes = [api("POST", "/v1/chat", json=body("ciao")).json()["route"] for _ in range(11)]
    assert routes == ["remote"] * 10 + ["local"]


@respx.mock
def test_stream_emits_route_tokens_done(api):
    enable()
    respx.post(CF_URL).mock(return_value=httpx.Response(200, content=sse("Ci", "ao", usage_neurons=9)))
    res = api("POST", "/v1/chat/stream", json=body("ciao"))
    ev = frames(res.text)
    assert ev[0] == ("route", {"route": "remote"})
    assert [d["text"] for e, d in ev if e == "token"] == ["Ci", "ao"]
    assert ev[-1][0] == "done"
    assert ev[-1][1]["meta"]["neurons"] == 9 and ev[-1][1]["meta"]["notice"] is None


@respx.mock
def test_stream_local_route_only_done(api):
    ev = frames(api("POST", "/v1/chat/stream", json=body()).text)
    assert ev == [("route", {"route": "local"}), ("done", {"meta": {"notice": None}})]


class _Dropping(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'data: {"choices":[{"delta":{"content":"Ciao "}}]}\n\n'
        raise httpx.ReadError("connection dropped")


@respx.mock
def test_stream_provider_drop_mid_reply_emits_done_with_notice(api):
    enable()
    respx.post(CF_URL).mock(return_value=httpx.Response(200, stream=_Dropping()))
    ev = frames(api("POST", "/v1/chat/stream", json=body("ciao")).text)
    assert ev[0][0] == "route" and ev[0][1]["route"] == "remote"
    assert [d["text"] for e, d in ev if e == "token"] == ["Ciao "]
    last = ev[-1]
    assert last[0] == "done"
    assert last[1]["meta"]["notice"] == "cloud_unavailable" and last[1]["meta"]["partial"] is True


@respx.mock
def test_stream_failure_before_first_token_routes_local(api):
    enable()
    respx.post(CF_URL).mock(return_value=httpx.Response(503))
    ev = frames(api("POST", "/v1/chat/stream", json=body("ciao")).text)
    assert ev == [("route", {"route": "local"}), ("done", {"meta": {"notice": "cloud_unavailable"}})]


@respx.mock
def test_stream_placeholder_split_across_tokens_unmasked(api):
    enable()
    respx.post(CF_URL).mock(
        return_value=httpx.Response(200, content=sse("Ciao ", "[PERS", "ONA_1]", " e fine."))
    )
    known = {"persons": ["Paolo Verdi"]}
    ev = frames(api("POST", "/v1/chat/stream",
                    json=body("Scrivi a Paolo Verdi", known_entities=known)).text)
    tokens = [d["text"] for e, d in ev if e == "token"]
    assert "".join(tokens) == "Ciao Paolo Verdi e fine."
    assert not any("[" in t or "PERSONA" in t for t in tokens)


@respx.mock
def test_cloudflare_down_allowlisted_user_served_by_gemini_fallback(api, monkeypatch):
    monkeypatch.setenv("AI_TEST_ALLOWLIST", "7")
    monkeypatch.setenv("AI_FALLBACK_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "g-SECRET")
    enable()
    respx.post(CF_URL).mock(return_value=httpx.Response(503))
    gem = respx.post(GEM_URL).mock(return_value=ok("da gemini"))
    res = api("POST", "/v1/chat", json=body()).json()
    assert res["route"] == "remote" and res["meta"]["provider"] == "gemini"
    assert res["meta"]["neurons"] == 0 and res["text"] == "da gemini"
    assert IBAN not in sent_text(gem)
    assert gem.calls[0].request.headers["authorization"] == "Bearer g-SECRET"


@respx.mock
def test_gemini_fallback_when_breaker_open_for_allowlisted(api, monkeypatch):
    monkeypatch.setenv("AI_TEST_ALLOWLIST", "7")
    monkeypatch.setenv("AI_FALLBACK_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "g-SECRET")
    enable()
    quota.trip_breaker(quota.next_midnight(NOW))
    cf = respx.post(CF_URL).mock(return_value=ok())
    respx.post(GEM_URL).mock(return_value=ok("g"))
    res = api("POST", "/v1/chat", json=body()).json()
    assert res["meta"]["provider"] == "gemini" and not cf.called


@respx.mock
def test_gemini_fallback_never_used_for_non_allowlisted_user(api, monkeypatch):
    monkeypatch.setenv("AI_TEST_ALLOWLIST", "7")
    monkeypatch.setenv("AI_FALLBACK_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "g-SECRET")
    enable(user=8)
    respx.post(CF_URL).mock(return_value=httpx.Response(503))
    gem = respx.post(GEM_URL).mock(return_value=ok())
    res = api("POST", "/v1/chat", user=8, json=body()).json()
    assert res["route"] == "local" and res["meta"]["notice"] == "cloud_unavailable"
    assert gem.call_count == 0


@respx.mock
def test_ledger_written_without_prompt_text(api):
    enable()
    respx.post(CF_URL).mock(return_value=ok("risposta segreta"))
    api("POST", "/v1/chat", json=body())
    rows = [dict(r) for r in db.connect().execute("SELECT * FROM ai_usage")]
    assert len(rows) == 1 and rows[0]["outcome"] == "ok" and rows[0]["neurons"] == 11
    dumped = json.dumps(rows)
    assert IBAN not in dumped and "risposta segreta" not in dumped


@respx.mock
def test_log_records_contain_no_prompt_or_reply(api, caplog):
    enable()
    respx.post(CF_URL).mock(return_value=ok("risposta segreta"))
    with caplog.at_level(logging.DEBUG):
        api("POST", "/v1/chat", json=body())
        api("POST", "/v1/chat/stream", json=body())
    text = caplog.text
    for secret in (IBAN, "paolo.verdi", "risposta segreta", "cf-SECRET-token"):
        assert secret not in text


def test_chat_requires_auth():
    from fastapi.testclient import TestClient

    from main import app

    assert TestClient(app).post("/v1/chat", json=body()).status_code == 401


def test_unknown_feature_is_422(api):
    assert api("POST", "/v1/chat", json=body(feature="nope")).status_code == 422
