"""Route + service tests for /goals (FOR-002): real Pazuru data, not a
localStorage mock. No entitlement gating (Goals has no REGISTRY entry in
auth/entitlements.py), so a single auth-only user fixture is used throughout."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi.testclient import TestClient

import goals_router as gr
import goals_service as gs
import main
from auth.dependencies import get_current_user

_USER = {
    "id": 1,
    "email": "u1@test.local",
    "tier": "free",
    "audience": "base",
    "household_id": None,
    "is_admin": False,
}

_GOAL_OUT = {
    "id": 7,
    "name": "Emergency fund",
    "target_cents": 500000,
    "saved_cents": 100000,
    "currency": "EUR",
    "deadline": None,
    "monthly_contribution_cents": 20000,
    "projected_completion": None,
    "is_achieved": False,
    "pct_complete": 20.0,
}


def _override_user():
    main.app.dependency_overrides[get_current_user] = lambda: _USER


def _clear_override():
    main.app.dependency_overrides.pop(get_current_user, None)


# ─── Service layer (Pazuru HTTP boundary mocked) ───────────────────────────


class _FakeResponse:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status
        self.text = str(payload)

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "http://pazuru.test/api/goals")
            raise httpx.HTTPStatusError(
                str(self.status_code),
                request=request,
                response=httpx.Response(self.status_code, request=request),
            )


class _FakeClient:
    def __init__(self, response: _FakeResponse | Exception) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        if isinstance(self._response, Exception):
            raise self._response
        return self._response

    async def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def test_list_goals_returns_real_pazuru_data(monkeypatch):
    monkeypatch.setattr(
        gs.httpx, "AsyncClient", lambda **_: _FakeClient(_FakeResponse([_GOAL_OUT]))
    )
    result = asyncio.run(gs.list_goals(cookie="tok", stepup_pazuru="su"))
    assert result["degraded"] is False
    assert result["goals"] == [_GOAL_OUT]


def test_list_goals_degrades_on_pazuru_outage(monkeypatch):
    monkeypatch.setattr(
        gs.httpx, "AsyncClient", lambda **_: _FakeClient(RuntimeError("pazuru down"))
    )
    result = asyncio.run(gs.list_goals(cookie="tok", stepup_pazuru="su"))
    assert result == {"goals": [], "degraded": True}


def test_create_goal_forwards_real_data(monkeypatch):
    monkeypatch.setattr(
        gs.httpx, "AsyncClient", lambda **_: _FakeClient(_FakeResponse(_GOAL_OUT, 201))
    )
    body = {"name": "Emergency fund", "target_cents": 500000}
    result = asyncio.run(gs.create_goal(body, cookie="tok", stepup_pazuru="su"))
    assert result == _GOAL_OUT


def test_update_goal_forwards_real_404(monkeypatch):
    """A goal that doesn't exist (or isn't owned by the caller) must surface as a
    real 404 — not be silently swallowed into a degraded/None response, which
    would let the UI believe the update succeeded."""
    monkeypatch.setattr(
        gs.httpx,
        "AsyncClient",
        lambda **_: _FakeClient(_FakeResponse({"detail": "Goal not found"}, 404)),
    )
    try:
        asyncio.run(
            gs.update_goal(999, {"name": "x", "target_cents": 1}, cookie="tok", stepup_pazuru="su")
        )
        raise AssertionError("expected HTTPException")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404


def test_create_goal_forwards_real_validation_error(monkeypatch):
    """Pazuru's target_cents: Field(ge=0) validation error (422) must reach the
    caller intact, not be degraded to None."""
    monkeypatch.setattr(
        gs.httpx,
        "AsyncClient",
        lambda **_: _FakeClient(_FakeResponse({"detail": "target_cents must be >= 0"}, 422)),
    )
    try:
        asyncio.run(
            gs.create_goal({"name": "x", "target_cents": -1}, cookie="tok", stepup_pazuru="su")
        )
        raise AssertionError("expected HTTPException")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422


def test_delete_goal_unavailable_returns_502(monkeypatch):
    monkeypatch.setattr(
        gs.httpx, "AsyncClient", lambda **_: _FakeClient(RuntimeError("pazuru down"))
    )
    try:
        asyncio.run(gs.delete_goal(7, cookie="tok", stepup_pazuru="su"))
        raise AssertionError("expected HTTPException")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 502


# ─── Route layer (service mocked) ──────────────────────────────────────────


async def _fake_list_goals(*, cookie=None, stepup_pazuru=None):
    return {"goals": [_GOAL_OUT], "degraded": False, "_cookie_seen": cookie}


def test_route_list_goals_returns_real_data(monkeypatch):
    monkeypatch.setattr(gr.goals_service, "list_goals", _fake_list_goals)
    _override_user()
    try:
        client = TestClient(main.app)
        resp = client.get("/goals", cookies={"suite_session": "tok-99"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["goals"] == [_GOAL_OUT]
        assert body["_cookie_seen"] == "tok-99"
    finally:
        _clear_override()


def test_route_list_goals_requires_auth():
    client = TestClient(main.app)
    resp = client.get("/goals")
    assert resp.status_code == 401


async def _fake_create_goal(body, *, cookie=None, stepup_pazuru=None):
    return {**_GOAL_OUT, **body, "id": 8}


def test_route_create_goal_returns_real_created_goal(monkeypatch):
    monkeypatch.setattr(gr.goals_service, "create_goal", _fake_create_goal)
    _override_user()
    try:
        client = TestClient(main.app)
        resp = client.post("/goals", json={"name": "Vacation", "target_cents": 200000})
        assert resp.status_code == 201
        assert resp.json()["id"] == 8
        assert resp.json()["name"] == "Vacation"
    finally:
        _clear_override()


async def _fake_update_goal_404(goal_id, body, *, cookie=None, stepup_pazuru=None):
    from fastapi import HTTPException

    raise HTTPException(404, "Goal not found")


def test_route_update_goal_forwards_404(monkeypatch):
    monkeypatch.setattr(gr.goals_service, "update_goal", _fake_update_goal_404)
    _override_user()
    try:
        client = TestClient(main.app)
        resp = client.put("/goals/999", json={"name": "x", "target_cents": 1})
        assert resp.status_code == 404
    finally:
        _clear_override()


async def _fake_delete_goal(goal_id, *, cookie=None, stepup_pazuru=None):
    return None


def test_route_delete_goal(monkeypatch):
    monkeypatch.setattr(gr.goals_service, "delete_goal", _fake_delete_goal)
    _override_user()
    try:
        client = TestClient(main.app)
        resp = client.delete("/goals/7")
        assert resp.status_code == 204
    finally:
        _clear_override()
