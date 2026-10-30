import pytest
from conftest import GATEWAY_TOKEN
from fastapi import FastAPI
from fastapi.testclient import TestClient

import consent
import db

app = FastAPI()
app.include_router(consent.router)
client = TestClient(app)


@pytest.fixture
def hdr(make_token):
    def _h(user=7):
        return {
            "X-AI-Gateway-Token": GATEWAY_TOKEN,
            "Authorization": f"Bearer {make_token(sub=str(user))}",
        }

    return _h


def test_reaccept_after_withdraw_grants():
    conn = db.connect()
    consent.record(conn, 7, "cloudflare", "accept", None)
    consent.record(conn, 7, "cloudflare", "withdraw", None)
    assert not consent.is_granted(conn, 7, "cloudflare")
    consent.record(conn, 7, "cloudflare", "accept", None)
    assert consent.is_granted(conn, 7, "cloudflare")


def test_old_version_consent_not_granted():
    conn = db.connect()
    conn.execute(
        "INSERT INTO ai_consents(user_id, provider, action, version, at) "
        "VALUES (7, 'cloudflare', 'accept', '2025-01-01', '2025-01-01T00:00:00Z')"
    )
    conn.commit()
    assert not consent.is_granted(conn, 7, "cloudflare")


def test_consent_routes_roundtrip_and_isolation(hdr):
    assert (
        client.post(
            "/v1/consents", json={"provider": "cloudflare"}, headers=hdr(7)
        ).status_code
        == 204
    )
    mine = {c["provider"]: c for c in client.get("/v1/consents", headers=hdr(7)).json()}
    other = {
        c["provider"]: c for c in client.get("/v1/consents", headers=hdr(8)).json()
    }
    assert mine["cloudflare"]["granted"] is True
    assert mine["cloudflare"]["version"] == consent.CONSENT_VERSION
    assert other["cloudflare"]["granted"] is False
    assert client.delete("/v1/consents/cloudflare", headers=hdr(7)).status_code == 204
    again = {
        c["provider"]: c for c in client.get("/v1/consents", headers=hdr(7)).json()
    }
    assert again["cloudflare"]["granted"] is False


def test_unknown_provider_422(hdr):
    assert (
        client.post(
            "/v1/consents", json={"provider": "evil"}, headers=hdr()
        ).status_code
        == 422
    )
    assert client.delete("/v1/consents/evil", headers=hdr()).status_code == 422


def test_consent_routes_require_auth():
    assert client.get("/v1/consents").status_code == 401
