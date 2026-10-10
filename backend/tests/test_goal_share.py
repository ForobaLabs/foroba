"""Goal what-if projection + signed share links (Plan AQ D9, ID-07)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import goal_share as gs
import main
from auth.dependencies import get_current_user
from rate_limit import limiter

_USER = {"id": 42, "email": "private@test.local", "tier": "free", "audience": "base",
         "household_id": None, "is_admin": False}

_BODY = {"name": "Holiday", "currency": "EUR", "saved_cents": 100_000,
         "target_cents": 300_000, "monthly_cents": 50_000, "rate_pct": 0.0}


@pytest.fixture()
def client():
    limiter.reset()
    main.app.dependency_overrides[get_current_user] = lambda: _USER
    yield TestClient(main.app)
    main.app.dependency_overrides.pop(get_current_user, None)


def test_projection_without_interest_is_linear():
    p = gs.project_series(100_000, 300_000, 50_000, 0.0)
    assert p["series"] == [100_000, 150_000, 200_000, 250_000, 300_000]
    assert p["months_to_target"] == 4


def test_projection_with_interest_beats_linear():
    flat = gs.project_series(100_000, 1_000_000, 50_000, 0.0)["months_to_target"]
    grown = gs.project_series(100_000, 1_000_000, 50_000, 8.0)["months_to_target"]
    assert grown < flat


def test_projection_already_reached_and_unreachable():
    assert gs.project_series(500, 400, 0, 0.0) == {"series": [500], "months_to_target": 0}
    p = gs.project_series(0, 100, 0, 0.0)
    assert p["months_to_target"] is None and len(p["series"]) == gs.MAX_MONTHS + 1


def test_token_roundtrip_contains_no_pii(client):
    r = client.post("/share/goal", json=_BODY)
    assert r.status_code == 201
    token = r.json()["token"]
    payload = client.get(f"/share/goal/{token}").json()
    assert payload["name"] == "Holiday" and payload["months_to_target"] == 4
    dump = json.dumps(payload) + token
    assert "private@test.local" not in dump and '"id"' not in json.dumps(payload)
    assert "user" not in json.dumps(payload).lower()


def test_public_read_needs_no_auth(client):
    token = client.post("/share/goal", json=_BODY).json()["token"]
    main.app.dependency_overrides.pop(get_current_user, None)
    assert TestClient(main.app).get(f"/share/goal/{token}").status_code == 200


def test_tampered_token_is_400(client):
    token = client.post("/share/goal", json=_BODY).json()["token"]
    body, sig = token.split(".")
    forged = gs._b64(json.dumps({**gs.verify_token(token), "name": "Evil"}).encode())
    for bad in (f"{forged}.{sig}", f"{body}.{sig[:-2]}AA", "garbage", f"{body}."):
        assert client.get(f"/share/goal/{bad}").status_code == 400


def test_expired_token_is_400(client):
    payload = gs.build_payload(name="Old", currency="EUR", saved_cents=0,
                               target_cents=100, monthly_cents=10, rate_pct=0.0, now=1_000)
    token = gs.issue_token(payload)
    assert client.get(f"/share/goal/{token}").status_code == 400
    with pytest.raises(gs.ShareTokenError):
        gs.verify_token(token)
    assert gs.verify_token(token, now=1_000 + gs.SHARE_TTL_SECONDS - 1)["name"] == "Old"


def test_create_requires_auth_and_validates(client):
    assert client.post("/share/goal", json={**_BODY, "rate_pct": 9.0}).status_code == 422
    assert client.post("/share/goal", json={**_BODY, "target_cents": 0}).status_code == 422
    main.app.dependency_overrides.pop(get_current_user, None)
    assert TestClient(main.app).post("/share/goal", json=_BODY).status_code in (401, 403)
