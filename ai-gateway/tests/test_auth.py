import time

from conftest import GATEWAY_TOKEN
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from auth import Caller, require_caller, require_internal

app = FastAPI()


@app.get("/whoami")
def whoami(caller: Caller = Depends(require_caller)):  # noqa: B008
    return {
        "user_id": caller.user_id,
        "tier": caller.tier,
        "is_admin": caller.is_admin,
    }


@app.get("/internal")
def internal(_: None = Depends(require_internal)):
    return {"ok": True}


client = TestClient(app)


def _h(token=None, bearer=None):
    h = {}
    if token is not None:
        h["X-AI-Gateway-Token"] = token
    if bearer is not None:
        h["Authorization"] = f"Bearer {bearer}"
    return h


def test_missing_gateway_token_401(make_token):
    assert client.get("/whoami", headers=_h(bearer=make_token())).status_code == 401


def test_wrong_gateway_token_401(make_token):
    r = client.get("/whoami", headers=_h("nope", make_token()))
    assert r.status_code == 401


def test_valid_token_but_no_jwt_401():
    assert client.get("/whoami", headers=_h(GATEWAY_TOKEN)).status_code == 401


def test_jwt_wrong_typ_401(make_token):
    r = client.get("/whoami", headers=_h(GATEWAY_TOKEN, make_token(typ="stepup")))
    assert r.status_code == 401


def test_expired_jwt_401(make_token):
    r = client.get(
        "/whoami", headers=_h(GATEWAY_TOKEN, make_token(exp=int(time.time()) - 5))
    )
    assert r.status_code == 401


def test_valid_caller_resolved(make_token):
    r = client.get("/whoami", headers=_h(GATEWAY_TOKEN, make_token()))
    assert r.status_code == 200
    assert r.json() == {"user_id": 7, "tier": "premium", "is_admin": False}


def test_internal_requires_only_gateway_token():
    assert client.get("/internal").status_code == 401
    assert client.get("/internal", headers=_h("nope")).status_code == 401
    assert client.get("/internal", headers=_h(GATEWAY_TOKEN)).status_code == 200
