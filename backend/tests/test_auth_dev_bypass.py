"""AUTH_DEV_BYPASS parity for get_current_user — mirrors Pazuru/Tsumi's require_auth.

Root cause (VF sprint, PZ-6/PZ-7 investigation): foroba/dev.sh sets AUTH_DEV_BYPASS=true
when starting the Foroba backend (like Pazuru's and Tsumi's dev.sh do for their own
auth modules), but auth/dependencies.py::get_current_user never implemented the bypass
check — so every entitlement-gated feature (LockedFeature/useEntitlement in @foroba/ui,
used by Pazuru's Taxes/Chat pages and others) always 401s on /auth/entitlements when
there is no real suite_session cookie, causing `visible` to default to False and the
whole feature to render blank.
"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import main
from auth.conn import get_conn
from auth.dependencies import get_current_user


def _app():
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: None

    @app.get("/protected")
    def protected(user: dict = Depends(get_current_user)) -> dict:
        return {"id": user["id"], "tier": user["tier"], "audience": user["audience"]}

    return TestClient(app)


def test_dev_bypass_allows_without_cookie(monkeypatch):
    monkeypatch.setenv("AUTH_DEV_BYPASS", "true")
    r = _app().get("/protected")
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "free"
    assert body["audience"] == "base"


def test_dev_bypass_disabled_requires_cookie(monkeypatch):
    monkeypatch.setenv("AUTH_DEV_BYPASS", "false")
    assert _app().get("/protected").status_code == 401


def test_dev_bypass_me_route_matches_response_model(monkeypatch):
    """Regression: /auth/me is declared response_model=UserPublic, so FastAPI
    validates the dev-bypass stub against that schema — a mismatched stub
    (invalid email, missing fields) raised a 500 ResponseValidationError that
    the isolated /protected route above never exercised (no response_model).
    """
    monkeypatch.setenv("AUTH_DEV_BYPASS", "true")
    client = TestClient(main.app)
    r = client.get("/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "free"
    assert body["audience"] == "base"
    assert body["totp_enabled"] is False
