from fastapi.testclient import TestClient

from main import app


def test_jwks_endpoint_returns_key_set():
    client = TestClient(app)
    resp = client.get("/.well-known/jwks.json")
    assert resp.status_code == 200
    body = resp.json()
    assert "keys" in body
    assert len(body["keys"]) == 1
    jwk = body["keys"][0]
    assert jwk["kty"] == "RSA"
    assert jwk["alg"] == "RS256"
    assert jwk["use"] == "sig"
    assert "kid" in jwk
    assert "n" in jwk and "e" in jwk
