"""Handoff uses an opaque one-time code redeemed back-channel (foroba#300, AI-6-F1/F3)."""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import handoff
import handoff_router
from auth.dependencies import get_current_user
from config import settings
from rate_limit import limiter


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    handoff._codes.clear()
    limiter.reset()
    monkeypatch.setattr(settings, "internal_api_token", "right-token", raising=False)
    monkeypatch.setattr(settings, "pazuru_app_url", "https://pz.test", raising=False)
    monkeypatch.setattr(settings, "tsumi_app_url", "https://ts.test", raising=False)


def _issue(app="tsumi", redirect="/portfolio", stepup="STEP"):
    return handoff.issue_handoff_code(
        user_id=5, app=app, redirect=redirect, sess="SESS-JWT", stepup=stepup
    )


def test_code_is_opaque_and_carries_no_session():
    code = _issue()
    assert "SESS-JWT" not in code and "STEP" not in code
    assert len(code) >= 40 and "." not in code  # not a JWT


def test_redeem_returns_payload_once():
    code = _issue()
    out = handoff.redeem_handoff_code(code, expected_app="tsumi")
    assert out == {"sess": "SESS-JWT", "stepup": "STEP", "redirect": "/portfolio", "user_id": 5}
    with pytest.raises(handoff.HandoffTokenError):
        handoff.redeem_handoff_code(code, expected_app="tsumi")


def test_redeem_wrong_app_consumes_nothing_useful():
    code = _issue(app="tsumi")
    with pytest.raises(handoff.HandoffTokenError):
        handoff.redeem_handoff_code(code, expected_app="pazuru")


def test_redeem_expired(monkeypatch):
    code = _issue()
    handoff._codes[code]["exp"] = time.time() - 1
    with pytest.raises(handoff.HandoffTokenError):
        handoff.redeem_handoff_code(code, expected_app="tsumi")


def test_store_is_bounded(monkeypatch):
    monkeypatch.setattr(handoff, "_MAX_CODES", 3)
    for _ in range(10):
        _issue()
    assert len(handoff._codes) <= 3


def _client():
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(handoff_router.router)
    app.include_router(handoff_router.internal_router)
    app.dependency_overrides[get_current_user] = lambda: {"id": 5}
    return TestClient(app, follow_redirects=False)


def test_mint_redirects_with_code_not_jwt():
    c = _client()
    c.cookies.set("suite_session", "SESS-JWT")
    r = c.get("/auth/handoff/tsumi?redirect=/portfolio")
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("https://ts.test/api/v1/tsumi/auth/handoff?code=")
    assert "SESS-JWT" not in loc and "token=" not in loc


def test_redeem_endpoint_requires_internal_token():
    code = _issue()
    c = _client()
    r = c.post("/internal/handoff/redeem", json={"code": code, "app": "tsumi"})
    assert r.status_code == 403
    r = c.post("/internal/handoff/redeem", json={"code": code, "app": "tsumi"},
               headers={"X-Internal-Token": "wrong"})
    assert r.status_code == 403
    # still redeemable afterwards: failed auth must not burn the code
    ok = c.post("/internal/handoff/redeem", json={"code": code, "app": "tsumi"},
                headers={"X-Internal-Token": "right-token"})
    assert ok.status_code == 200 and ok.json()["sess"] == "SESS-JWT"


def test_redeem_endpoint_second_use_is_401():
    code = _issue()
    c = _client()
    h = {"X-Internal-Token": "right-token"}
    body = {"code": code, "app": "tsumi"}
    assert c.post("/internal/handoff/redeem", json=body, headers=h).status_code == 200
    assert c.post("/internal/handoff/redeem", json=body, headers=h).status_code == 401


def test_redeem_endpoint_fails_closed_when_token_unset(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_token", "", raising=False)
    code = _issue()
    r = _client().post("/internal/handoff/redeem", json={"code": code, "app": "tsumi"},
                       headers={"X-Internal-Token": ""})
    assert r.status_code == 403
