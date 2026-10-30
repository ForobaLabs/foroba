"""Chat pipeline: resolve route -> quota -> mask -> provider (+fallback) -> unmask -> ledger.

Only metadata is logged or stored; prompts, replies and keys never reach logs or the ledger.
"""

import json
import logging
import re
import time
from collections.abc import AsyncIterator
from contextlib import closing
from dataclasses import dataclass
from typing import Literal

import anyio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import byok
import db
import features
import prefs
import quota
import usage
from auth import Caller, require_caller
from config import get_settings
from masking import engine
from providers import openai_compat
from providers.base import ChatRequest, ProviderError
from providers.registry import PROVIDERS, ProviderSpec

router = APIRouter(prefix="/v1", tags=["chat"])
log = logging.getLogger("ai_gateway")

_PARTIAL_PLACEHOLDER = re.compile(r"\[[A-Za-z_0-9 ]{0,31}$")


class KnownIn(BaseModel):
    persons: list[str] = []
    orgs: list[str] = []
    addresses: list[str] = []


class ChatIn(BaseModel):
    app: str
    feature: str
    task: Literal["chat", "tools", "extract", "long"] = "chat"
    messages: list[dict] = Field(min_length=1)
    tools: list[dict] | None = None
    json_mode: bool = False
    known_entities: KnownIn | None = None


@dataclass
class Target:
    provider: str
    spec: ProviderSpec
    api_key: str
    account_id: str | None
    model: str


@dataclass
class Local:
    notice: str | None


@dataclass
class Plan:
    caller: Caller
    body: ChatIn
    mode: str
    targets: list[Target]
    messages: list[dict]
    mapping: engine.Mapping

    def request(self, target: Target) -> ChatRequest:
        return ChatRequest(
            messages=self.messages,
            model=target.model,
            tools=self.body.tools,
            json_mode=self.body.json_mode,
        )


def _task_model(task: str) -> str:
    s = get_settings()
    return {
        "chat": s.model_chat,
        "tools": s.model_tools,
        "extract": s.model_extract,
        "long": s.model_long,
    }[task]


def _cloudflare_target(task: str) -> Target | None:
    s = get_settings()
    if not (s.cf_account_id and s.cf_api_token):
        return None
    return Target(
        "cloudflare", PROVIDERS["cloudflare"], s.cf_api_token, s.cf_account_id, _task_model(task)
    )


def _gemini_target(caller: Caller) -> Target | None:
    """Test-period fallback: only for allowlisted users (free tier may train on prompts)."""
    s = get_settings()
    if s.fallback_provider != "gemini" or not s.gemini_api_key:
        return None
    if caller.user_id not in s.test_allowlist:
        return None
    return Target("gemini", PROVIDERS["gemini"], s.gemini_api_key, None, s.model_fallback)


def _ledger(conn, caller, body, provider, model, neurons, started, outcome) -> None:
    usage.record(
        conn,
        caller,
        body.app,
        body.feature,
        body.task,
        provider,
        model,
        neurons,
        int((time.monotonic() - started) * 1000),
        outcome,
    )


async def _prepare(conn, caller: Caller, body: ChatIn) -> Plan | Local:
    try:
        features.validate(body.app, body.feature)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    res = prefs.resolve(conn, caller, body.app, body.feature)
    if res.mode == "local":
        return Local(res.notice)
    started = time.monotonic()
    notice, reason = quota.check_detail(conn, caller, res.mode)
    targets: list[Target] = []
    if res.mode == "cloud":
        cf = _cloudflare_target(body.task)
        fallback = _gemini_target(caller)
        if notice and reason in ("breaker", "suite") and fallback:
            targets, notice = [fallback], None
        elif not notice:
            targets = [t for t in (cf, fallback) if t]
            if not targets:
                notice = "cloud_unavailable"
    elif not notice:
        try:
            key, account_id, model = byok.load_key(conn, caller.user_id, res.byok_provider)
        except byok.KeyNotFound:
            return Local("byok_key_invalid")
        spec = PROVIDERS[res.byok_provider]
        targets = [Target(res.byok_provider, spec, key, account_id, model or spec.models[0])]
    if notice:
        _ledger(conn, caller, body, res.mode, "", 0, started, f"blocked_{reason or 'config'}")
        return Local(notice)
    known = body.known_entities or KnownIn()
    try:
        messages, mapping = await anyio.to_thread.run_sync(
            engine.mask_messages,
            body.messages,
            engine.KnownEntities(known.persons, known.orgs, known.addresses),
        )
    except engine.MaskingError:
        _ledger(conn, caller, body, res.mode, "", 0, started, "mask_error")
        return Local("cloud_unavailable")
    return Plan(caller, body, res.mode, targets, messages, mapping)


def _on_error(conn, plan: Plan, target: Target, exc: ProviderError, started: float) -> tuple[bool, str]:
    """Ledger + side effects for a provider failure. Returns (stop_trying, notice)."""
    _ledger(conn, plan.caller, plan.body, target.provider, target.model, 0, started, exc.kind)
    log.warning("provider_error provider=%s kind=%s status=%s", target.provider, exc.kind, exc.status)
    if exc.kind == "auth" and plan.mode == "byok":
        byok.mark_invalid(conn, plan.caller.user_id, target.provider)
        return True, "byok_key_invalid"
    if exc.kind == "quota" and plan.mode == "cloud" and target.provider == "cloudflare":
        quota.trip_breaker(quota.next_midnight(usage.now()), conn)
    return exc.kind == "bad_request", "cloud_unavailable"


def _unmask_calls(calls: list, mapping: engine.Mapping) -> list:
    out = []
    for call in calls:
        call = dict(call)
        fn = dict(call.get("function") or {})
        if isinstance(fn.get("arguments"), str):
            fn["arguments"] = engine.unmask(fn["arguments"], mapping)
        call["function"] = fn
        out.append(call)
    return out


def _meta(plan: Plan, target: Target, model: str, neurons: int, **extra) -> dict:
    return {
        "provider": target.provider,
        "model": model,
        "neurons": neurons,
        "masked_count": len(plan.mapping),
        "notice": None,
        **extra,
    }


@router.post("/chat")
async def chat(body: ChatIn, caller: Caller = Depends(require_caller)):  # noqa: B008
    with closing(db.connect()) as conn:
        plan = await _prepare(conn, caller, body)
        if isinstance(plan, Local):
            return {"route": "local", "meta": {"notice": plan.notice}}
        notice = "cloud_unavailable"
        for target in plan.targets:
            started = time.monotonic()
            try:
                result = await openai_compat.complete(
                    target.spec, target.api_key, target.account_id, plan.request(target)
                )
            except ProviderError as exc:
                stop, notice = _on_error(conn, plan, target, exc, started)
                if stop:
                    break
                continue
            _ledger(conn, caller, body, target.provider, result.model, result.neurons, started, "ok")
            log.info("chat provider=%s model=%s neurons=%s", target.provider, result.model, result.neurons)
            return {
                "route": "remote",
                "text": engine.unmask(result.text, plan.mapping),
                "tool_calls": _unmask_calls(result.tool_calls, plan.mapping),
                "meta": _meta(plan, target, result.model, result.neurons),
            }
        return {"route": "local", "meta": {"notice": notice}}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _split_safe(buf: str) -> tuple[str, str]:
    """Hold back a trailing, not yet closed `[LABEL_n` so placeholders split across tokens unmask."""
    m = _PARTIAL_PLACEHOLDER.search(buf)
    return (buf[: m.start()], buf[m.start() :]) if m else (buf, "")


async def _local_stream(notice: str | None) -> AsyncIterator[str]:
    yield _sse("route", {"route": "local"})
    yield _sse("done", {"meta": {"notice": notice}})


async def _first_event(agen):
    try:
        return await anext(agen)
    except StopAsyncIteration:
        return None


async def _remote_stream(plan: Plan) -> AsyncIterator[str]:
    conn = db.connect()
    try:
        notice = "cloud_unavailable"
        for target in plan.targets:
            started = time.monotonic()
            agen = openai_compat.stream(
                target.spec, target.api_key, target.account_id, plan.request(target)
            )
            try:
                first = await _first_event(agen)
            except ProviderError as exc:
                stop, notice = _on_error(conn, plan, target, exc, started)
                if stop:
                    break
                continue
            async for frame in _relay(conn, plan, target, agen, first, started):
                yield frame
            return
        yield _sse("route", {"route": "local"})
        yield _sse("done", {"meta": {"notice": notice}})
    finally:
        conn.close()


async def _relay(conn, plan: Plan, target: Target, agen, first, started: float) -> AsyncIterator[str]:
    yield _sse("route", {"route": "remote"})
    mapping = plan.mapping
    buf, neurons = "", 0

    async def events():
        if first is not None:
            yield first
        async for ev in agen:
            yield ev

    try:
        async for ev in events():
            if ev["type"] == "token":
                safe, buf = _split_safe(buf + ev["text"])
                if safe:
                    yield _sse("token", {"text": engine.unmask(safe, mapping)})
            elif ev["type"] == "tool_calls":
                yield _sse("tool_calls", {"calls": _unmask_calls(ev["calls"], mapping)})
            elif ev["type"] == "usage":
                neurons = ev["neurons"]
    except ProviderError as exc:
        _on_error(conn, plan, target, exc, started)
        meta = _meta(plan, target, target.model, 0, notice="cloud_unavailable", partial=True)
        yield _sse("done", {"meta": meta})
        return
    if buf:
        yield _sse("token", {"text": engine.unmask(buf, mapping)})
    _ledger(conn, plan.caller, plan.body, target.provider, target.model, neurons, started, "ok")
    log.info("chat_stream provider=%s model=%s neurons=%s", target.provider, target.model, neurons)
    yield _sse("done", {"meta": _meta(plan, target, target.model, neurons)})


@router.post("/chat/stream")
async def chat_stream(body: ChatIn, caller: Caller = Depends(require_caller)):  # noqa: B008
    with closing(db.connect()) as conn:
        plan = await _prepare(conn, caller, body)
    gen = _local_stream(plan.notice) if isinstance(plan, Local) else _remote_stream(plan)
    return StreamingResponse(
        gen, media_type="text/event-stream", headers={"Cache-Control": "no-store"}
    )
