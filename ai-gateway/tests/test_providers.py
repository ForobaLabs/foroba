import json

import httpx
import pytest
import respx

from providers import openai_compat
from providers.base import ChatRequest, ProviderError
from providers.registry import ALLOWED_HOSTS, PROVIDERS, ProviderSpec

KEY = "sk-test-SECRET123"
MSGS = [{"role": "user", "content": "ciao"}]


def _req(**kw):
    return ChatRequest(messages=MSGS, model="m", **kw)


def _ok(neurons=None, content="ok"):
    usage = {"prompt_tokens": 1, "completion_tokens": 1}
    if neurons is not None:
        usage["neurons"] = neurons
    return {"choices": [{"message": {"role": "assistant", "content": content}}], "usage": usage}


@pytest.mark.asyncio
@respx.mock
async def test_cloudflare_url_built_with_account_id():
    route = respx.post(
        "https://api.cloudflare.com/client/v4/accounts/acc123/ai/v1/chat/completions"
    ).mock(return_value=httpx.Response(200, json=_ok(neurons=42)))
    res = await openai_compat.complete(PROVIDERS["cloudflare"], KEY, "acc123", _req())
    assert route.called
    assert res.text == "ok" and res.neurons == 42
    assert route.calls[0].request.headers["authorization"] == f"Bearer {KEY}"


@pytest.mark.asyncio
@respx.mock
async def test_other_providers_not_metered():
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_ok(neurons=99))
    )
    res = await openai_compat.complete(PROVIDERS["openai"], KEY, None, _req())
    assert res.neurons == 0


@pytest.mark.asyncio
async def test_disallowed_host_blocked():
    evil = ProviderSpec(base_url="https://evil.example/v1", models=("m",), needs_account_id=False)
    with pytest.raises(ProviderError) as ei:
        await openai_compat.complete(evil, KEY, None, _req())
    assert ei.value.kind == "bad_request"
    assert "evil.example" not in ALLOWED_HOSTS


@pytest.mark.asyncio
@respx.mock
async def test_401_maps_to_auth():
    respx.post("https://api.openai.com/v1/chat/completions").mock(return_value=httpx.Response(401))
    with pytest.raises(ProviderError) as ei:
        await openai_compat.complete(PROVIDERS["openai"], KEY, None, _req())
    assert ei.value.kind == "auth"


@pytest.mark.asyncio
@respx.mock
async def test_4006_maps_to_quota():
    respx.post("https://api.cloudflare.com/client/v4/accounts/a/ai/v1/chat/completions").mock(
        return_value=httpx.Response(400, json={"errors": [{"code": 4006, "message": "limit"}]})
    )
    with pytest.raises(ProviderError) as ei:
        await openai_compat.complete(PROVIDERS["cloudflare"], KEY, "a", _req())
    assert ei.value.kind == "quota"


@pytest.mark.asyncio
@respx.mock
async def test_429_5xx_and_4xx_mapping():
    url = "https://api.mistral.ai/v1/chat/completions"
    for status, kind in ((429, "quota"), (503, "unavailable"), (422, "bad_request")):
        respx.post(url).mock(return_value=httpx.Response(status))
        with pytest.raises(ProviderError) as ei:
            await openai_compat.complete(PROVIDERS["mistral"], KEY, None, _req())
        assert ei.value.kind == kind


@pytest.mark.asyncio
@respx.mock
async def test_timeout_maps_to_unavailable():
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=httpx.ReadTimeout("slow")
    )
    with pytest.raises(ProviderError) as ei:
        await openai_compat.complete(PROVIDERS["openai"], KEY, None, _req())
    assert ei.value.kind == "unavailable"


@pytest.mark.asyncio
@respx.mock
async def test_error_message_never_contains_key():
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(401, text=f"bad key {KEY}")
    )
    with pytest.raises(ProviderError) as ei:
        await openai_compat.complete(PROVIDERS["openai"], KEY, None, _req())
    assert KEY not in str(ei.value) and KEY not in repr(ei.value)
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=httpx.ConnectError(f"boom {KEY}")
    )
    with pytest.raises(ProviderError) as ei:
        await openai_compat.complete(PROVIDERS["openai"], KEY, None, _req())
    assert KEY not in str(ei.value) and KEY not in repr(ei.value)


@pytest.mark.asyncio
@respx.mock
async def test_stream_yields_tokens_then_usage():
    sse = (
        'data: {"choices":[{"delta":{"content":"Ci"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"ao"}}]}\n\n'
        'data: {"choices":[],"usage":{"neurons":7}}\n\n'
        "data: [DONE]\n\n"
    )
    respx.post("https://api.cloudflare.com/client/v4/accounts/a/ai/v1/chat/completions").mock(
        return_value=httpx.Response(200, content=sse, headers={"content-type": "text/event-stream"})
    )
    events = [
        e async for e in openai_compat.stream(PROVIDERS["cloudflare"], KEY, "a", _req(stream=True))
    ]
    assert [e["text"] for e in events if e["type"] == "token"] == ["Ci", "ao"]
    assert events[-1] == {"type": "usage", "neurons": 7}


@pytest.mark.asyncio
@respx.mock
async def test_stream_accumulates_tool_calls():
    sse = (
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"c1","function":'
        '{"name":"f","arguments":"{\\"a\\""}}]}}]}\n\n'
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":'
        '{"arguments":":1}"}}]}}]}\n\n'
        "data: [DONE]\n\n"
    )
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, content=sse)
    )
    events = [
        e async for e in openai_compat.stream(PROVIDERS["openai"], KEY, None, _req(stream=True))
    ]
    calls = next(e for e in events if e["type"] == "tool_calls")["calls"]
    assert calls[0]["id"] == "c1"
    assert calls[0]["function"] == {"name": "f", "arguments": '{"a":1}'}


@pytest.mark.asyncio
@respx.mock
async def test_json_mode_sets_response_format():
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_ok())
    )
    await openai_compat.complete(PROVIDERS["openai"], KEY, None, _req(json_mode=True))
    body = json.loads(route.calls[0].request.content)
    assert body["response_format"] == {"type": "json_object"}
    assert body["model"] == "m" and body["stream"] is False


def test_allowed_hosts_derived_from_registry():
    assert "api.cloudflare.com" in ALLOWED_HOSTS and "openrouter.ai" in ALLOWED_HOSTS
    assert set(PROVIDERS) == {"cloudflare", "openai", "anthropic", "mistral", "gemini", "openrouter"}


@pytest.mark.asyncio
@respx.mock
async def test_stream_coerces_non_string_content_to_text():
    # Workers AI parses numeric-looking tokens as JSON numbers ("content": 2026).
    sse = (
        'data: {"choices":[{"delta":{"content":"Nel "}}]}\n\n'
        'data: {"choices":[{"delta":{"content":2026}}]}\n\n'
        'data: {"choices":[{"delta":{"content":0}}]}\n\n'
        "data: [DONE]\n\n"
    )
    respx.post("https://api.cloudflare.com/client/v4/accounts/a/ai/v1/chat/completions").mock(
        return_value=httpx.Response(200, content=sse, headers={"content-type": "text/event-stream"})
    )
    events = [
        e async for e in openai_compat.stream(PROVIDERS["cloudflare"], KEY, "a", _req(stream=True))
    ]
    assert [e["text"] for e in events if e["type"] == "token"] == ["Nel ", "2026", "0"]


@pytest.mark.asyncio
@respx.mock
async def test_complete_coerces_non_string_content_to_text():
    respx.post("https://api.cloudflare.com/client/v4/accounts/a/ai/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_ok(content=2026))
    )
    res = await openai_compat.complete(PROVIDERS["cloudflare"], KEY, "a", _req())
    assert res.text == "2026"
