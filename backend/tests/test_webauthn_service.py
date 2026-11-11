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
        "INSERT INTO webauthn_credentials "
        "(user_id, credential_id, public_key, sign_count, label, rp_id) "
        "VALUES (?, ?, ?, 0, 'k', ?)",
        (user_id, bytes_to_base64url(raw_id), bytes_to_base64url(b"pk"), settings.webauthn_rp_id),
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


# --- Task 2b: stale-passkey detection (credentials bound to a previous RP ID) ---


def _add_cred(conn, user_id, raw_id: bytes, rp_id: str | None) -> None:
    conn.execute(
        "INSERT INTO webauthn_credentials "
        "(user_id, credential_id, public_key, sign_count, label, rp_id) "
        "VALUES (?, ?, ?, 0, 'k', ?)",
        (user_id, bytes_to_base64url(raw_id), bytes_to_base64url(b"pk"), rp_id),
    )
    conn.commit()


def test_init_schema_has_rp_id():
    conn, _ = _conn_with_user()
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(webauthn_credentials)")]
    assert "rp_id" in cols


def test_init_schema_adds_and_backfills_rp_id_on_legacy_table(monkeypatch):
    monkeypatch.setenv("WEBAUTHN_RP_ID", "foroba-app.duckdns.org")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE webauthn_credentials (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " user_id INTEGER NOT NULL, credential_id TEXT NOT NULL UNIQUE,"
        " public_key TEXT NOT NULL, sign_count INTEGER NOT NULL DEFAULT 0, label TEXT,"
        " created_at TEXT NOT NULL DEFAULT (datetime('now')));"
        "INSERT INTO webauthn_credentials (user_id, credential_id, public_key)"
        " VALUES (1, 'c', 'p');"
    )
    init_schema(conn)
    row = conn.execute("SELECT rp_id FROM webauthn_credentials").fetchone()
    assert row["rp_id"] == "foroba-app.duckdns.org"


def test_registration_stores_current_rp_id(monkeypatch):
    monkeypatch.setattr(settings, "webauthn_rp_id", "forobalabs.com")
    fake = MagicMock(
        return_value=MagicMock(credential_id=b"id", credential_public_key=b"pk", sign_count=0)
    )
    monkeypatch.setattr(passkey_service.webauthn, "verify_registration_response", fake)
    monkeypatch.setattr(passkey_service, "parse_registration_credential_json", lambda j: j)
    conn, user_id = _conn_with_user()
    store_challenge(conn, user_id, bytes_to_base64url(b"r" * 32), purpose="registration")
    verify_registration(conn, user_id, "{}", label="k")
    row = conn.execute("SELECT rp_id FROM webauthn_credentials").fetchone()
    assert row["rp_id"] == "forobalabs.com"


def test_auth_options_exclude_stale_credentials(monkeypatch):
    monkeypatch.setattr(settings, "webauthn_rp_id", "forobalabs.com")
    conn, user_id = _conn_with_user()
    _add_cred(conn, user_id, b"old", "foroba-app.duckdns.org")
    opts = json.loads(passkey_service.authentication_options_for_user(conn, user_id))
    assert opts["allowCredentials"] == []
    _add_cred(conn, user_id, b"new", "forobalabs.com")
    opts = json.loads(passkey_service.authentication_options_for_user(conn, user_id))
    assert [c["id"] for c in opts["allowCredentials"]] == [bytes_to_base64url(b"new")]


def test_reenrol_needed_states(monkeypatch):
    monkeypatch.setattr(settings, "webauthn_rp_id", "forobalabs.com")
    conn, user_id = _conn_with_user()
    assert passkey_service.reenrol_needed(conn, user_id) is False  # no credentials
    _add_cred(conn, user_id, b"old", "foroba-app.duckdns.org")
    assert passkey_service.reenrol_needed(conn, user_id) is True  # stale only
    _add_cred(conn, user_id, b"null", None)
    assert passkey_service.reenrol_needed(conn, user_id) is True  # unknown RP counts as stale
    _add_cred(conn, user_id, b"new", "forobalabs.com")
    assert passkey_service.reenrol_needed(conn, user_id) is False  # one current is enough
    assert passkey_service.has_current_credential(conn, user_id) is True


def test_verify_authentication_rejects_sign_count_regression(monkeypatch):
    """Pre-beta Task 2.2 row 8: a counter that does not advance (cloned authenticator) is
    refused by the real library, and the stored counter is left untouched."""
    import hashlib

    from webauthn.helpers.exceptions import InvalidAuthenticationResponse

    monkeypatch.setattr(settings, "webauthn_origin", "https://app.forobalabs.com")
    conn, user_id = _conn_with_credential(b"cred-2")
    conn.execute("UPDATE webauthn_credentials SET sign_count = 5")
    conn.commit()
    challenge = b"c" * 32
    store_challenge(conn, user_id, bytes_to_base64url(challenge), purpose="authentication")
    cred = json.loads(_auth_credential_json(challenge, "https://app.forobalabs.com", b"cred-2"))
    rp_hash = hashlib.sha256(settings.webauthn_rp_id.encode()).digest()
    cred["response"]["authenticatorData"] = bytes_to_base64url(
        rp_hash + b"\x01" + (3).to_bytes(4, "big")
    )
    with pytest.raises(InvalidAuthenticationResponse, match="sign count"):
        verify_authentication(conn, user_id, json.dumps(cred))
    assert conn.execute("SELECT sign_count FROM webauthn_credentials").fetchone()[0] == 5
