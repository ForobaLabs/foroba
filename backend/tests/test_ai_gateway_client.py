"""Plan AV T7 — Foroba's client for the isolated ai-gateway."""

import httpx
import pytest
import respx

from ai_gateway_client import GatewayClient, GatewayRejected, GatewayUnavailable

pytestmark = pytest.mark.asyncio

BASE = "http://gw.test"


@pytest.fixture
def gw():
    return GatewayClient(BASE, "s3cret-token")


@respx.mock
async def test_chat_forwards_jwt_and_gateway_token(gw):
    route = respx.post(f"{BASE}/v1/chat").mock(
        return_value=httpx.Response(200, json={"route": "local", "meta": {}})
    )
    out = await gw.chat("jwt.abc.def", {"app": "foroba", "feature": "jeli"})
    assert out["route"] == "local"
    sent = route.calls[0].request
    assert sent.headers["authorization"] == "Bearer jwt.abc.def"
    assert sent.headers["x-ai-gateway-token"] == "s3cret-token"


@respx.mock
async def test_server_error_raises_unavailable(gw):
    respx.get(f"{BASE}/v1/prefs").mock(return_value=httpx.Response(500))
    with pytest.raises(GatewayUnavailable):
        await gw.get("jwt", "/v1/prefs")


@respx.mock
async def test_gateway_401_means_misconfigured_so_unavailable(gw):
    respx.get(f"{BASE}/v1/prefs").mock(return_value=httpx.Response(401))
    with pytest.raises(GatewayUnavailable):
        await gw.get("jwt", "/v1/prefs")


@respx.mock
async def test_transport_error_raises_unavailable(gw):
    respx.get(f"{BASE}/v1/prefs").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(GatewayUnavailable):
        await gw.get("jwt", "/v1/prefs")


@respx.mock
async def test_422_is_passed_through_as_rejected(gw):
    respx.put(f"{BASE}/v1/byok").mock(
        return_value=httpx.Response(422, json={"detail": {"code": "byok_test_failed"}})
    )
    with pytest.raises(GatewayRejected) as ei:
        await gw.put("jwt", "/v1/byok", {"provider": "openai"})
    assert ei.value.status == 422
    assert ei.value.detail == {"code": "byok_test_failed"}


@respx.mock
async def test_204_returns_none(gw):
    respx.delete(f"{BASE}/v1/byok/openai").mock(return_value=httpx.Response(204))
    assert await gw.delete("jwt", "/v1/byok/openai") is None


@respx.mock
async def test_stream_yields_parsed_events(gw):
    body = (
        'event: route\ndata: {"route":"remote"}\n\n'
        'event: token\ndata: {"text":"Ciao"}\n\n'
        'event: done\ndata: {"meta":{}}\n\n'
    )
    respx.post(f"{BASE}/v1/chat/stream").mock(
        return_value=httpx.Response(
            200, content=body.encode(), headers={"content-type": "text/event-stream"}
        )
    )
    events = [e async for e in gw.stream("jwt", {"app": "foroba"})]
    assert events == [
        ("route", {"route": "remote"}),
        ("token", {"text": "Ciao"}),
        ("done", {"meta": {}}),
    ]


@respx.mock
async def test_stream_error_status_raises_unavailable(gw):
    respx.post(f"{BASE}/v1/chat/stream").mock(return_value=httpx.Response(503))
    with pytest.raises(GatewayUnavailable):
        _ = [e async for e in gw.stream("jwt", {})]


@respx.mock
async def test_export_and_delete_user_use_token_only(gw):
    exp = respx.get(f"{BASE}/v1/users/7/export").mock(
        return_value=httpx.Response(200, json={"consents": []})
    )
    dele = respx.delete(f"{BASE}/v1/users/7").mock(return_value=httpx.Response(204))
    assert await gw.export_user(7) == {"consents": []}
    await gw.delete_user(7)
    for route in (exp, dele):
        req = route.calls[0].request
        assert req.headers["x-ai-gateway-token"] == "s3cret-token"
        assert "authorization" not in req.headers


@respx.mock
async def test_purge_pending_retries_and_clears_only_successes(gw):
    import sqlite3

    from ai_gateway_client import list_pending_deletes, purge_pending, record_pending_delete

    conn = sqlite3.connect(":memory:")
    for uid in (1, 2):
        record_pending_delete(conn, uid)
    respx.delete(f"{BASE}/v1/users/1").mock(return_value=httpx.Response(204))
    respx.delete(f"{BASE}/v1/users/2").mock(return_value=httpx.Response(500))
    done, failed = await purge_pending(conn, gw)
    assert (done, failed) == (1, 1)
    assert list_pending_deletes(conn) == [2]
