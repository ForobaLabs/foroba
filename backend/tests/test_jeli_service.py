import httpx
import pytest

import jeli_service


class _RaisingStreamCtx:
    def __init__(self, exc):
        self._exc = exc

    async def __aenter__(self):
        raise self._exc

    async def __aexit__(self, *args):
        return False


async def _collect(gen):
    return [chunk async for chunk in gen]


@pytest.mark.asyncio
async def test_stream_chat_ollama_unreachable_completes_gracefully(monkeypatch):
    """Ollama refusing the connection must not crash the widget — the stream
    should complete normally (no exception) with no content, letting the
    frontend show its 'AI offline' fallback instead of a hard connection reset."""
    def fake_stream(self, method, url, **kwargs):
        return _RaisingStreamCtx(httpx.ConnectError("Connection refused"))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)

    chunks = await _collect(jeli_service.stream_chat("system prompt", "hello"))
    assert chunks == []


@pytest.mark.asyncio
async def test_stream_chat_ollama_http_error_completes_gracefully(monkeypatch):
    """A non-2xx from Ollama (e.g. model not pulled) must also degrade gracefully."""
    def fake_stream(self, method, url, **kwargs):
        exc = httpx.HTTPStatusError(
            "500", request=httpx.Request(method, url), response=httpx.Response(500)
        )
        return _RaisingStreamCtx(exc)

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)

    chunks = await _collect(jeli_service.stream_chat("system prompt", "hello"))
    assert chunks == []
