import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import jwt
import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GATEWAY_TOKEN = "test-gateway-token-0123456789abcdef"

os.environ.update(
    {
        "AI_GATEWAY_TOKEN": GATEWAY_TOKEN,
        "FOROBA_JWKS_URL": "http://foroba.invalid/.well-known/jwks.json",
        "AI_GATEWAY_DB_KEY": "test-db-key",
        "AI_GATEWAY_FIELD_KEY": Fernet.generate_key().decode(),
    }
)


@pytest.fixture(scope="session")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def gateway_env(monkeypatch, tmp_path, rsa_key):
    """Per-test settings (fresh DB file) and a JWKS client that serves the test key."""
    monkeypatch.setenv("AI_GATEWAY_DB_PATH", str(tmp_path / "ai_gateway.db"))
    import auth
    import config

    config.get_settings.cache_clear()
    public = rsa_key.public_key()
    fake = SimpleNamespace(
        get_signing_key_from_jwt=lambda _t: SimpleNamespace(key=public)
    )
    monkeypatch.setattr(auth, "_jwks_client", lambda: fake)
    yield
    config.get_settings.cache_clear()


@pytest.fixture
def make_token(rsa_key):
    pem = rsa_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    def _make(**over) -> str:
        now = int(time.time())
        claims = {
            "sub": "7",
            "typ": "session",
            "iss": "foroba",
            "iat": now,
            "exp": now + 600,
            "tier": "premium",
            "is_admin": False,
        }
        claims.update(over)
        return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": "k1"})

    return _make


@pytest.fixture(autouse=True)
def _reset_quota_state():
    import quota

    quota.reset()
    yield
    quota.reset()


@pytest.fixture
def api(make_token):
    """Authenticated call helper: api("POST", "/v1/chat", user=7, tier="free", json=...)."""
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)

    def call(method, path, user=7, tier="free", admin=False, **kw):
        headers = {
            "X-AI-Gateway-Token": GATEWAY_TOKEN,
            "Authorization": "Bearer "
            + make_token(sub=str(user), tier=tier, is_admin=admin),
        }
        return client.request(method, path, headers=headers, **kw)

    return call
