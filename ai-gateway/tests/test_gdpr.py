import httpx
import pytest
import respx

import consent
import db
import prefs
import usage
from auth import Caller

OPENAI = "https://api.openai.com/v1/chat/completions"
KEY = "sk-live-ABCDEFGH1234567890WXYZ"
TOKEN = {"X-AI-Gateway-Token": "test-gateway-token-0123456789abcdef"}


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from main import app

    return TestClient(app)


@pytest.fixture
def seeded(api):
    with respx.mock:
        respx.post(OPENAI).mock(
            return_value=httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})
        )
        api("PUT", "/v1/byok", json={"provider": "openai", "api_key": KEY, "model": "gpt-4o-mini"})
    conn = db.connect()
    consent.record(conn, 7, "cloudflare", "accept", "1.2.3.4")
    prefs.put(conn, 7, "pazuru", "chat", "cloud", None)
    usage.record(conn, Caller(7, "free", False), "pazuru", "chat", "chat", "cloudflare", "m", 40, 5, "ok")
    usage.record(conn, Caller(8, "free", False), "pazuru", "chat", "chat", "cloudflare", "m", 60, 5, "ok")
    consent.record(conn, 8, "cloudflare", "accept", None)
    prefs.put(conn, 8, "tsumi", "jeli", "cloud", None)
    return conn


def test_export_contains_no_secret(client, seeded):
    res = client.get("/v1/users/7/export", headers=TOKEN)
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"consents", "prefs", "byok", "usage_months"}
    assert body["byok"][0]["provider"] == "openai" and "last4" not in body["byok"][0]
    assert KEY not in res.text and KEY[-4:] not in res.text
    assert body["prefs"][0]["feature"] == "chat"
    assert body["usage_months"][0]["neurons"] == 40 and body["usage_months"][0]["requests"] == 1
    assert "1.2.3.4" in res.text  # the user's own consent record, ip included


def test_delete_user_wipes_all_tables(client, seeded):
    assert client.delete("/v1/users/7", headers=TOKEN).status_code == 204
    for table in ("ai_consents", "ai_prefs", "byok_keys", "ai_usage"):
        assert seeded.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id=7").fetchone()[0] == 0
    for table in ("ai_consents", "ai_prefs", "ai_usage"):
        assert seeded.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id=8").fetchone()[0] == 1


@pytest.mark.parametrize("method,path", [("get", "/v1/users/7/export"), ("delete", "/v1/users/7")])
def test_gdpr_routes_reject_missing_token(client, seeded, method, path):
    assert getattr(client, method)(path).status_code == 401
    assert getattr(client, method)(path, headers={"X-AI-Gateway-Token": "wrong"}).status_code == 401
    assert seeded.execute("SELECT COUNT(*) FROM ai_prefs WHERE user_id=7").fetchone()[0] == 1
