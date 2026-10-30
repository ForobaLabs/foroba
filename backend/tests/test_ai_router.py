"""Plan AV T8 — ai_router: local|cloud|byok routing with local fallback (Foroba)."""

import json

import httpx
import pytest
import respx

import ai_router
from config import settings
from jeli_output_guard import sanitize_reply

BASE = "http://gw.test"
pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _gw(monkeypatch):
    monkeypatch.setattr(settings, "ai_gateway_url", BASE)
    monkeypatch.setattr(settings, "ai_gateway_token", "gw-tok")


def _ctx(jwt="jwt-1", feature="jeli"):
    return ai_router.AiContext(
        jwt=jwt, app="foroba", feature=feature, known_entities=ai_router.KnownEntities()
    )


async def _local():
    return ai_router.AiOutcome(text="local text")


async def _local_stream():
    for t in ("loc", "al"):
        yield t


def _sse(*frames):
    return "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in frames)


@respx.mock
async def test_local_pref_never_calls_gateway_when_gateway_says_local():
    route = respx.post(f"{BASE}/v1/chat").mock(
        return_value=httpx.Response(200, json={"route": "local", "meta": {"notice": None}})
    )
    out = await ai_router.complete(
        _ctx(), task="chat", messages=[{"role": "user", "content": "x"}], local=_local
    )
    assert route.call_count == 1
    assert out.text == "local text" and out.provider == "local" and out.notice is None


@respx.mock
async def test_remote_route_returns_gateway_text_with_meta():
    respx.post(f"{BASE}/v1/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "route": "remote",
                "text": "cloud text",
                "tool_calls": [],
                "meta": {"provider": "cloudflare", "model": "m1", "neurons": 5, "notice": None},
            },
        )
    )
    out = await ai_router.complete(
        _ctx(), task="chat", messages=[{"role": "user", "content": "x"}], local=_local
    )
    assert (out.text, out.provider, out.model) == ("cloud text", "cloudflare", "m1")


@respx.mock
async def test_gateway_route_local_runs_local_with_notice():
    respx.post(f"{BASE}/v1/chat").mock(
        return_value=httpx.Response(
            200, json={"route": "local", "meta": {"notice": "plan_quota_exhausted"}}
        )
    )
    out = await ai_router.complete(
        _ctx(), task="chat", messages=[{"role": "user", "content": "x"}], local=_local
    )
    assert out.text == "local text" and out.notice == "plan_quota_exhausted"


@respx.mock
async def test_gateway_unreachable_runs_local_with_notice():
    respx.post(f"{BASE}/v1/chat").mock(side_effect=httpx.ConnectError("down"))
    out = await ai_router.complete(
        _ctx(), task="chat", messages=[{"role": "user", "content": "x"}], local=_local
    )
    assert out.text == "local text" and out.notice == "cloud_unavailable"


@respx.mock
async def test_gateway_5xx_runs_local_with_notice():
    respx.post(f"{BASE}/v1/chat").mock(return_value=httpx.Response(500))
    out = await ai_router.complete(
        _ctx(), task="chat", messages=[{"role": "user", "content": "x"}], local=_local
    )
    assert out.notice == "cloud_unavailable"


@respx.mock
async def test_scheduler_context_without_jwt_is_local():
    route = respx.post(f"{BASE}/v1/chat").mock(return_value=httpx.Response(500))
    out = await ai_router.complete(
        _ctx(jwt=None, feature="monthly_report"),
        task="long",
        messages=[{"role": "user", "content": "x"}],
        local=_local,
    )
    assert route.call_count == 0 and out.text == "local text" and out.notice is None


@respx.mock
async def test_request_body_carries_app_feature_task_and_entities():
    route = respx.post(f"{BASE}/v1/chat").mock(
        return_value=httpx.Response(200, json={"route": "local", "meta": {"notice": None}})
    )
    ctx = ai_router.AiContext(
        jwt="j",
        app="foroba",
        feature="jeli",
        known_entities=ai_router.KnownEntities(persons=["Ada Rossi"]),
    )
    await ai_router.complete(
        ctx, task="chat", messages=[{"role": "user", "content": "x"}], local=_local
    )
    body = json.loads(route.calls[0].request.content)
    assert (body["app"], body["feature"], body["task"]) == ("foroba", "jeli", "chat")
    assert body["known_entities"]["persons"] == ["Ada Rossi"]
    assert route.calls[0].request.headers["authorization"] == "Bearer j"


@respx.mock
async def test_output_guard_applied_to_remote_text():
    respx.post(f"{BASE}/v1/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "route": "remote",
                "text": "You have €98765.43 saved.",
                "meta": {"provider": "cloudflare", "model": "m", "notice": None},
            },
        )
    )
    out = await ai_router.complete(
        _ctx(), task="chat", messages=[{"role": "user", "content": "x"}], local=_local
    )
    guarded = sanitize_reply(out.text, context_text="no figures here")
    assert guarded != out.text  # ungrounded figure is refused/treated exactly as for local


@respx.mock
async def test_stream_remote_yields_tokens_then_done_meta():
    body = _sse(
        ("route", {"route": "remote"}),
        ("token", {"text": "he"}),
        ("token", {"text": "llo"}),
        ("done", {"meta": {"provider": "cloudflare", "model": "m", "notice": None}}),
    )
    respx.post(f"{BASE}/v1/chat/stream").mock(return_value=httpx.Response(200, text=body))
    frames = [
        f
        async for f in ai_router.stream(
            _ctx(),
            task="chat",
            messages=[{"role": "user", "content": "x"}],
            local_stream=_local_stream,
        )
    ]
    assert "".join(f.text for f in frames if f.kind == "token") == "hello"
    assert frames[-1].kind == "done" and frames[-1].meta["provider"] == "cloudflare"


@respx.mock
async def test_stream_gateway_local_runs_local_stream_with_notice():
    body = _sse(("route", {"route": "local"}), ("done", {"meta": {"notice": "consent_required"}}))
    respx.post(f"{BASE}/v1/chat/stream").mock(return_value=httpx.Response(200, text=body))
    frames = [
        f
        async for f in ai_router.stream(
            _ctx(),
            task="chat",
            messages=[{"role": "user", "content": "x"}],
            local_stream=_local_stream,
        )
    ]
    assert "".join(f.text for f in frames if f.kind == "token") == "local"
    assert frames[-1].meta == {"provider": "local", "model": "", "notice": "consent_required"}


@respx.mock
async def test_stream_unreachable_runs_local_stream_with_notice():
    respx.post(f"{BASE}/v1/chat/stream").mock(side_effect=httpx.ConnectError("down"))
    frames = [
        f
        async for f in ai_router.stream(
            _ctx(),
            task="chat",
            messages=[{"role": "user", "content": "x"}],
            local_stream=_local_stream,
        )
    ]
    assert "".join(f.text for f in frames if f.kind == "token") == "local"
    assert frames[-1].meta["notice"] == "cloud_unavailable"


@respx.mock
async def test_stream_without_jwt_is_local_and_never_calls_gateway():
    route = respx.post(f"{BASE}/v1/chat/stream").mock(return_value=httpx.Response(500))
    frames = [
        f
        async for f in ai_router.stream(
            _ctx(jwt=None),
            task="chat",
            messages=[{"role": "user", "content": "x"}],
            local_stream=_local_stream,
        )
    ]
    assert route.call_count == 0 and frames[-1].kind == "done"


# ── call sites pass the right (app, feature, task) ───────────────────────────


@respx.mock
async def test_generate_narrative_uses_monthly_report_long_and_stays_local_without_jwt(monkeypatch):
    import jeli_service

    captured = {}

    async def fake_complete(ctx, *, task, messages, tools=None, json_mode=False, local):
        captured.update(app=ctx.app, feature=ctx.feature, task=task, jwt=ctx.jwt)
        return await local()

    monkeypatch.setattr(ai_router, "complete", fake_complete)

    async def fake_local(*a, **k):
        return "narr"

    monkeypatch.setattr(jeli_service, "_ollama_narrative", fake_local)
    assert await jeli_service.generate_narrative("sys", "msg") == "narr"
    assert captured == {"app": "foroba", "feature": "monthly_report", "task": "long", "jwt": None}


@respx.mock
async def test_lab_codegen_uses_lab_feature(monkeypatch):
    import lab_service

    captured = {}

    async def fake_complete(ctx, *, task, messages, tools=None, json_mode=False, local):
        captured.update(app=ctx.app, feature=ctx.feature, task=task, json_mode=json_mode)
        return ai_router.AiOutcome(text='{"code": "x=1", "explanation": "e"}')

    monkeypatch.setattr(ai_router, "complete", fake_complete)
    ctx = ai_router.AiContext(
        jwt="j", app="foroba", feature="lab", known_entities=ai_router.KnownEntities()
    )
    out = await lab_service._generate_code_routed(ctx, "q", ["df"], [], "", None, None)
    assert out == {"code": "x=1", "explanation": "e"}
    assert captured == {"app": "foroba", "feature": "lab", "task": "tools", "json_mode": True}
