import json
import sqlite3
from unittest.mock import MagicMock

import pytest
from webauthn.helpers import bytes_to_base64url

from config import settings
from db import init_schema
from passkeys import service as passkey_service
from passkeys.service import (
    consume_challenge,
    registration_options_for_user,
    store_challenge,
    verify_authentication,
    verify_registration,
)


def _conn_with_user() -> tuple[sqlite3.Connection, int]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    conn.execute(
        "INSERT INTO users (email, password_hash, name) VALUES ('w@example.com', 'h', 'W')"
    )
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE email = 'w@example.com'").fetchone()["id"]
    return conn, user_id


def test_registration_options_returns_json_with_challenge():
    conn, user_id = _conn_with_user()
    options_json = registration_options_for_user(conn, user_id, "w@example.com")
    assert "challenge" in options_json
    row = conn.execute(
        "SELECT challenge, purpose FROM webauthn_challenges WHERE user_id = ?", (user_id,)
    ).fetchone()
    assert row["purpose"] == "registration"


def test_store_and_consume_challenge_round_trip():
    conn, user_id = _conn_with_user()
    store_challenge(conn, user_id, "abc123", purpose="authentication")
    challenge = consume_challenge(conn, user_id, purpose="authentication")
    assert challenge == "abc123"
    # single-use: gone after consuming
    assert consume_challenge(conn, user_id, purpose="authentication") is None


# --- Plan free-tier-infra Task 2: comma-separated origin list ---


def test_webauthn_origins_single(monkeypatch):
    monkeypatch.setattr(settings, "webauthn_origin", "https://foroba-app.duckdns.org")
    assert settings.webauthn_origins == ["https://foroba-app.duckdns.org"]


def test_webauthn_origins_list(monkeypatch):
    monkeypatch.setattr(
        settings,
        "webauthn_origin",
        "https://app.forobalabs.com, https://pazuru.forobalabs.com,,"
        "https://tsumi.forobalabs.com,https://m.forobalabs.com",
    )
    assert settings.webauthn_origins == [
        "https://app.forobalabs.com",
        "https://pazuru.forobalabs.com",
        "https://tsumi.forobalabs.com",
        "https://m.forobalabs.com",
    ]


def _auth_credential_json(challenge: bytes, origin: str, raw_id: bytes) -> str:
    client_data = json.dumps(
        {"type": "webauthn.get", "challenge": bytes_to_base64url(challenge), "origin": origin}
    ).encode()
    auth_data = b"\x00" * 32 + b"\x01" + b"\x00\x00\x00\x01"
    return json.dumps(
        {
            "id": bytes_to_base64url(raw_id),
            "rawId": bytes_to_base64url(raw_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(auth_data),
                "signature": bytes_to_base64url(b"sig"),
            },
        }
    )


def _conn_with_credential(raw_id: bytes) -> tuple[sqlite3.Connection, int]:
    conn, user_id = _conn_with_user()
    conn.execute(
        "INSERT INTO webauthn_credentials (user_id, credential_id, public_key, sign_count, label) "
        "VALUES (?, ?, ?, 0, 'k')",
        (user_id, bytes_to_base64url(raw_id), bytes_to_base64url(b"pk")),
    )
    conn.commit()
    return conn, user_id


def test_verify_authentication_accepts_listed_origin(monkeypatch):
    monkeypatch.setattr(
        settings, "webauthn_origin", "https://app.forobalabs.com,https://m.forobalabs.com"
    )
    fake = MagicMock(return_value=MagicMock(new_sign_count=2))
    monkeypatch.setattr(passkey_service.webauthn, "verify_authentication_response", fake)
    conn, user_id = _conn_with_credential(b"cred-1")
    challenge = b"c" * 32
    store_challenge(conn, user_id, bytes_to_base64url(challenge), purpose="authentication")
    cred = _auth_credential_json(challenge, "https://m.forobalabs.com", b"cred-1")
    assert verify_authentication(conn, user_id, cred) is True
    assert fake.call_args.kwargs["expected_origin"] == settings.webauthn_origins
    assert isinstance(fake.call_args.kwargs["expected_origin"], list)


def test_verify_registration_passes_origin_list(monkeypatch):
    monkeypatch.setattr(
        settings, "webauthn_origin", "https://app.forobalabs.com,https://m.forobalabs.com"
    )
    fake = MagicMock(
        return_value=MagicMock(credential_id=b"id", credential_public_key=b"pk", sign_count=0)
    )
    monkeypatch.setattr(passkey_service.webauthn, "verify_registration_response", fake)
    monkeypatch.setattr(passkey_service, "parse_registration_credential_json", lambda j: j)
    conn, user_id = _conn_with_user()
    store_challenge(conn, user_id, bytes_to_base64url(b"r" * 32), purpose="registration")
    verify_registration(conn, user_id, "{}", label="k")
    assert fake.call_args.kwargs["expected_origin"] == [
        "https://app.forobalabs.com",
        "https://m.forobalabs.com",
    ]


def test_verify_authentication_rejects_unlisted_origin(monkeypatch):
    from webauthn.helpers.exceptions import InvalidAuthenticationResponse

    monkeypatch.setattr(settings, "webauthn_origin", "https://app.forobalabs.com")
    conn, user_id = _conn_with_credential(b"cred-1")
    challenge = b"c" * 32
    store_challenge(conn, user_id, bytes_to_base64url(challenge), purpose="authentication")
    cred = _auth_credential_json(challenge, "https://evil.example", b"cred-1")
    with pytest.raises(InvalidAuthenticationResponse, match="origin"):
        verify_authentication(conn, user_id, cred)
