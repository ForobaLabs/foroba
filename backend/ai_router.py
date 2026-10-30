"""Plan AV T8 — route every AI call through the gateway (local|cloud|byok) with local fallback.

The gateway decides the route from the user's prefs, consent and quota. This module only
asks it and, whenever the answer is "local" (or the gateway is unreachable), runs the
caller-supplied local callable — the unchanged Ollama code. Output guards run at the call
site on the final text for both paths. A context without a JWT (scheduler jobs) never
reaches the gateway: there is no user session to authorise a cloud call.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field

from ai_gateway_client import GatewayRejected, GatewayUnavailable, get_client
from auth.dependencies import _token_from_header

logger = logging.getLogger(__name__)


@dataclass
class KnownEntities:
    persons: list[str] = field(default_factory=list)
    orgs: list[str] = field(default_factory=list)
    addresses: list[str] = field(default_factory=list)


@dataclass
class AiContext:
    jwt: str | None
    app: str
    feature: str
    known_entities: KnownEntities = field(default_factory=KnownEntities)
    last_meta: dict | None = None  # meta of the latest complete()/stream(), for ai_meta in replies


@dataclass
class AiOutcome:
    text: str = ""
    tool_calls: list = field(default_factory=list)
    provider: str = "local"
    model: str = ""
    notice: str | None = None

    def meta(self) -> dict:
        return {"provider": self.provider, "model": self.model, "notice": self.notice}


@dataclass
class AiFrame:
    kind: str  # "token" | "done"
    text: str = ""
    meta: dict = field(default_factory=dict)


def _body(ctx: AiContext, task: str, messages: list[dict], tools, json_mode: bool) -> dict:
    ke = ctx.known_entities
    return {
        "app": ctx.app,
        "feature": ctx.feature,
        "task": task,
        "messages": messages,
        "tools": tools,
        "json_mode": json_mode,
        "known_entities": {"persons": ke.persons, "orgs": ke.orgs, "addresses": ke.addresses},
    }


def _unavailable(exc: Exception) -> str:
    logger.warning("ai_gateway_fallback_local reason=%s", type(exc).__name__)
    return "cloud_unavailable"


async def _complete(
    ctx: AiContext,
    *,
    task: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    json_mode: bool = False,
    local: Callable[[], Awaitable[AiOutcome]],
) -> AiOutcome:
    if ctx.jwt is None:
        return await local()
    try:
        res = await get_client().chat(ctx.jwt, _body(ctx, task, messages, tools, json_mode))
    except (GatewayUnavailable, GatewayRejected) as exc:
        out = await local()
        out.notice = _unavailable(exc)
        return out
    meta = res.get("meta") or {}
    if res.get("route") == "remote":
        return AiOutcome(
            text=res.get("text") or "",
            tool_calls=res.get("tool_calls") or [],
            provider=meta.get("provider", "cloud"),
            model=meta.get("model", ""),
            notice=meta.get("notice"),
        )
    out = await local()
    out.notice = meta.get("notice")
    return out


async def complete(
    ctx: AiContext,
    *,
    task: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    json_mode: bool = False,
    local: Callable[[], Awaitable[AiOutcome]],
) -> AiOutcome:
    out = await _complete(
        ctx, task=task, messages=messages, tools=tools, json_mode=json_mode, local=local
    )
    ctx.last_meta = out.meta()
    return out


async def _local_frames(
    local_stream: Callable[[], AsyncIterator[str]], notice: str | None
) -> AsyncIterator[AiFrame]:
    async for chunk in local_stream():
        yield AiFrame("token", text=chunk)
    yield AiFrame("done", meta={"provider": "local", "model": "", "notice": notice})


async def stream(
    ctx: AiContext,
    *,
    task: str,
    messages: list[dict],
    local_stream: Callable[[], AsyncIterator[str]],
) -> AsyncIterator[AiFrame]:
    if ctx.jwt is None:
        async for f in _local_frames(local_stream, None):
            yield f
        return
    emitted = False
    notice: str | None = None
    try:
        route = "local"
        async for event, data in get_client().stream(
            ctx.jwt, _body(ctx, task, messages, None, False)
        ):
            if event == "route":
                route = data.get("route", "local")
            elif event == "token" and route == "remote":
                emitted = True
                yield AiFrame("token", text=data.get("text", ""))
            elif event == "done":
                meta = data.get("meta") or {}
                if route == "remote":
                    yield AiFrame(
                        "done",
                        meta={
                            "provider": meta.get("provider", "cloud"),
                            "model": meta.get("model", ""),
                            "notice": meta.get("notice"),
                        },
                    )
                    return
                notice = meta.get("notice")
    except (GatewayUnavailable, GatewayRejected) as exc:
        notice = _unavailable(exc)
        if emitted:
            # Tokens already left: a local re-run would duplicate the reply.
            yield AiFrame("done", meta={"provider": "cloud", "model": "", "notice": notice})
            return
    async for f in _local_frames(local_stream, notice):
        yield f


async def collect(frames: AsyncIterator[AiFrame]) -> tuple[str, dict]:
    """Drain a frame stream into (full text, done meta) for call sites that buffer."""
    parts: list[str] = []
    meta: dict = {"provider": "local", "model": "", "notice": None}
    async for f in frames:
        if f.kind == "token":
            parts.append(f.text)
        else:
            meta = f.meta
    return "".join(parts), meta


def context_for(
    user: dict | None, jwt: str | None, *, feature: str, app: str = "foroba"
) -> AiContext:
    persons = [n for n in ((user or {}).get("display_name"), (user or {}).get("name")) if n]
    return AiContext(
        jwt=jwt, app=app, feature=feature, known_entities=KnownEntities(persons=persons)
    )


def jwt_from(authorization: str | None, suite_session: str | None) -> str | None:
    """Session JWT to forward to the gateway: Bearer header first, then the cookie."""
    return _token_from_header(authorization) or suite_session or None
