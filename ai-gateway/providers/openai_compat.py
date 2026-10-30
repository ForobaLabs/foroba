"""OpenAI-compatible chat adapter used for Workers AI and every BYOK provider."""

import asyncio
import json
from collections.abc import AsyncIterator
from urllib.parse import urlsplit

import httpx

from .base import ChatRequest, ChatResult, ProviderError
from .registry import ALLOWED_HOSTS, ProviderSpec

TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)
FIRST_BYTE_S = 20.0
CF_QUOTA_CODE = 4006

_client: httpx.AsyncClient | None = None


async def _guard(request: httpx.Request) -> None:
    if request.url.host not in ALLOWED_HOSTS:
        raise ProviderError("bad_request")


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=TIMEOUT, event_hooks={"request": [_guard]})
    return _client


def _url(spec: ProviderSpec, account_id: str | None) -> str:
    if spec.needs_account_id and not account_id:
        raise ProviderError("bad_request")
    base = spec.base_url.format(account_id=account_id or "").rstrip("/")
    if urlsplit(base).hostname not in ALLOWED_HOSTS:
        raise ProviderError("bad_request")
    return f"{base}/chat/completions"


def _payload(req: ChatRequest) -> dict:
    body: dict = {"model": req.model, "messages": req.messages, "stream": req.stream}
    if req.tools:
        body["tools"] = req.tools
    if req.json_mode:
        body["response_format"] = {"type": "json_object"}
    return body


def _map_status(status: int, body: bytes) -> ProviderError:
    if status in (401, 403):
        return ProviderError("auth", status)
    if status == 429:
        return ProviderError("quota", status)
    if status >= 500:
        return ProviderError("unavailable", status)
    try:
        errors = json.loads(body).get("errors") or []
        if any(isinstance(e, dict) and e.get("code") == CF_QUOTA_CODE for e in errors):
            return ProviderError("quota", status)
    except (ValueError, AttributeError):
        pass
    return ProviderError("bad_request", status)


def _neurons(spec: ProviderSpec, usage: dict | None) -> int:
    if not spec.needs_account_id or not usage:
        return 0
    value = usage.get("neurons")
    return int(value) if isinstance(value, (int, float)) else 0


async def complete(
    spec: ProviderSpec, api_key: str, account_id: str | None, req: ChatRequest
) -> ChatResult:
    url = _url(spec, account_id)
    try:
        resp = await _get_client().post(
            url,
            json=_payload(ChatRequest(**{**req.__dict__, "stream": False})),
            headers={"Authorization": f"Bearer {api_key}"},
        )
    except ProviderError:
        raise
    except httpx.HTTPError:
        raise ProviderError("unavailable") from None
    if resp.status_code >= 400:
        raise _map_status(resp.status_code, resp.content)
    try:
        data = resp.json()
        message = data["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise ProviderError("unavailable", resp.status_code) from None
    return ChatResult(
        text=message.get("content") or "",
        tool_calls=message.get("tool_calls") or [],
        neurons=_neurons(spec, data.get("usage")),
        model=data.get("model") or req.model,
    )


async def stream(
    spec: ProviderSpec, api_key: str, account_id: str | None, req: ChatRequest
) -> AsyncIterator[dict]:
    url = _url(spec, account_id)
    calls: dict[int, dict] = {}
    neurons = 0
    try:
        async with _get_client().stream(
            "POST",
            url,
            json=_payload(ChatRequest(**{**req.__dict__, "stream": True})),
            headers={"Authorization": f"Bearer {api_key}"},
        ) as resp:
            if resp.status_code >= 400:
                raise _map_status(resp.status_code, await resp.aread())
            lines = resp.aiter_lines()
            first = True
            while True:
                try:
                    line = await (
                        asyncio.wait_for(anext(lines), FIRST_BYTE_S) if first else anext(lines)
                    )
                except StopAsyncIteration:
                    break
                first = False
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    data = json.loads(chunk)
                except ValueError:
                    continue
                neurons = _neurons(spec, data.get("usage")) or neurons
                for choice in data.get("choices") or []:
                    delta = choice.get("delta") or {}
                    if delta.get("content"):
                        yield {"type": "token", "text": delta["content"]}
                    for tc in delta.get("tool_calls") or []:
                        slot = calls.setdefault(
                            tc.get("index", 0),
                            {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                        )
                        slot["id"] = tc.get("id") or slot["id"]
                        fn = tc.get("function") or {}
                        slot["function"]["name"] += fn.get("name") or ""
                        slot["function"]["arguments"] += fn.get("arguments") or ""
    except ProviderError:
        raise
    except (httpx.HTTPError, TimeoutError):
        raise ProviderError("unavailable") from None
    if calls:
        yield {"type": "tool_calls", "calls": [calls[i] for i in sorted(calls)]}
    yield {"type": "usage", "neurons": neurons}
