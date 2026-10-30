"""Client for the isolated ai-gateway (Plan AV). The gateway alone holds provider credentials;
Foroba only forwards the caller's session JWT plus the shared X-AI-Gateway-Token."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx

from config import settings

_TIMEOUT = 20.0
# 404/422 carry a meaningful user-facing answer (no such key / invalid input / byok_test_failed);
# anything else non-2xx (incl. 401 = misconfigured token) means the gateway cannot be relied on.
_PASSTHROUGH = (404, 422)


class GatewayUnavailable(Exception):
    """Transport error or unusable gateway response."""


class GatewayRejected(Exception):
    def __init__(self, status: int, detail: Any):
        super().__init__(f"gateway rejected request ({status})")
        self.status = status
        self.detail = detail


def _detail(resp: httpx.Response) -> Any:
    try:
        return resp.json().get("detail")
    except (ValueError, AttributeError):
        return None


def _check(resp: httpx.Response) -> None:
    if resp.status_code in _PASSTHROUGH:
        raise GatewayRejected(resp.status_code, _detail(resp))
    if resp.status_code >= 300:
        raise GatewayUnavailable(f"gateway status {resp.status_code}")


class GatewayClient:
    def __init__(self, base_url: str, token: str):
        self._base = base_url.rstrip("/")
        self._token = token

    def _headers(self, jwt: str | None) -> dict[str, str]:
        h = {"X-AI-Gateway-Token": self._token}
        if jwt:
            h["Authorization"] = f"Bearer {jwt}"
        return h

    async def request(
        self, method: str, jwt: str | None, path: str, body: Any = None, params: Any = None
    ) -> Any:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.request(
                    method, self._base + path, headers=self._headers(jwt), json=body, params=params
                )
        except httpx.HTTPError as exc:
            raise GatewayUnavailable(type(exc).__name__) from None
        _check(resp)
        if resp.status_code == 204 or not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            raise GatewayUnavailable("non-json response") from None

    async def get(self, jwt: str, path: str, params: Any = None) -> Any:
        return await self.request("GET", jwt, path, params=params)

    async def put(self, jwt: str, path: str, body: Any) -> Any:
        return await self.request("PUT", jwt, path, body)

    async def post(self, jwt: str, path: str, body: Any = None) -> Any:
        return await self.request("POST", jwt, path, body)

    async def delete(self, jwt: str, path: str) -> Any:
        return await self.request("DELETE", jwt, path)

    async def chat(self, jwt: str, body: dict) -> dict:
        return await self.request("POST", jwt, "/v1/chat", body)

    async def stream(self, jwt: str, body: dict) -> AsyncIterator[tuple[str, dict]]:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                async with c.stream(
                    "POST", self._base + "/v1/chat/stream", headers=self._headers(jwt), json=body
                ) as resp:
                    if resp.status_code >= 300:
                        raise GatewayUnavailable(f"gateway status {resp.status_code}")
                    event = "message"
                    async for line in resp.aiter_lines():
                        if line.startswith("event:"):
                            event = line[6:].strip()
                        elif line.startswith("data:"):
                            try:
                                yield event, json.loads(line[5:].strip())
                            except ValueError:
                                raise GatewayUnavailable("bad sse frame") from None
                            event = "message"
        except httpx.HTTPError as exc:
            raise GatewayUnavailable(type(exc).__name__) from None

    async def export_user(self, user_id: int) -> dict:
        return await self.request("GET", None, f"/v1/users/{int(user_id)}/export")

    async def delete_user(self, user_id: int) -> None:
        await self.request("DELETE", None, f"/v1/users/{int(user_id)}")


def get_client() -> GatewayClient:
    return GatewayClient(settings.ai_gateway_url, settings.ai_gateway_token)


# ── Pending erasures (gateway unreachable at account deletion) ──────────────
# Own table created on demand: it must not leak into runtime_settings (admin-visible toggles).


def _ensure_pending(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS ai_gateway_pending_deletes "
        "(user_id INTEGER PRIMARY KEY, at TEXT NOT NULL)"
    )


def record_pending_delete(conn: sqlite3.Connection, user_id: int) -> None:
    _ensure_pending(conn)
    conn.execute(
        "INSERT OR IGNORE INTO ai_gateway_pending_deletes (user_id, at) VALUES (?, ?)",
        (user_id, datetime.now(UTC).isoformat()),
    )
    conn.commit()


def list_pending_deletes(conn: sqlite3.Connection) -> list[int]:
    _ensure_pending(conn)
    return [
        r[0] for r in conn.execute("SELECT user_id FROM ai_gateway_pending_deletes ORDER BY at")
    ]


def clear_pending_delete(conn: sqlite3.Connection, user_id: int) -> None:
    _ensure_pending(conn)
    conn.execute("DELETE FROM ai_gateway_pending_deletes WHERE user_id = ?", (user_id,))
    conn.commit()


async def purge_pending(conn: sqlite3.Connection, client: GatewayClient) -> tuple[int, int]:
    """Retry every deferred erasure; returns (done, still_failing)."""
    done = failed = 0
    for uid in list_pending_deletes(conn):
        try:
            await client.delete_user(uid)
        except Exception:
            failed += 1
        else:
            clear_pending_delete(conn, uid)
            done += 1
    return done, failed
