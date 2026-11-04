"""WebAuthn (passkey) registration + authentication ceremonies via py_webauthn.

Named `passkeys` (not `webauthn`) to avoid shadowing the installed `webauthn` pip package,
since this backend's modules are imported as flat top-level names (`from config import ...`),
not as a namespaced package.
"""

from __future__ import annotations

import sqlite3

import webauthn
from webauthn.helpers import (
    base64url_to_bytes,
    bytes_to_base64url,
    parse_authentication_credential_json,
    parse_registration_credential_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from config import settings


def store_challenge(
    conn: sqlite3.Connection, user_id: int, challenge: str, *, purpose: str
) -> None:
    conn.execute(
        "DELETE FROM webauthn_challenges WHERE user_id = ? AND purpose = ?", (user_id, purpose)
    )
    conn.execute(
        "INSERT INTO webauthn_challenges (user_id, challenge, purpose) VALUES (?, ?, ?)",
        (user_id, challenge, purpose),
    )
    conn.commit()


def consume_challenge(conn: sqlite3.Connection, user_id: int, *, purpose: str) -> str | None:
    row = conn.execute(
        "SELECT id, challenge FROM webauthn_challenges WHERE user_id = ? AND purpose = ?",
        (user_id, purpose),
    ).fetchone()
    if row is None:
        return None
    conn.execute("DELETE FROM webauthn_challenges WHERE id = ?", (row["id"],))
    conn.commit()
    return row["challenge"]


def registration_options_for_user(conn: sqlite3.Connection, user_id: int, email: str) -> str:
    existing = conn.execute(
        "SELECT credential_id FROM webauthn_credentials WHERE user_id = ?", (user_id,)
    ).fetchall()
    options = webauthn.generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=str(user_id).encode(),
        user_name=email,
        user_display_name=email,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(row["credential_id"]))
            for row in existing
        ],
    )
    store_challenge(conn, user_id, bytes_to_base64url(options.challenge), purpose="registration")
    return webauthn.options_to_json(options)


def verify_registration(
    conn: sqlite3.Connection, user_id: int, credential_json: str, *, label: str
) -> None:
    expected_challenge = consume_challenge(conn, user_id, purpose="registration")
    if expected_challenge is None:
        raise ValueError("No pending registration challenge for this user")
    credential = parse_registration_credential_json(credential_json)
    verification = webauthn.verify_registration_response(
        credential=credential,
        expected_challenge=base64url_to_bytes(expected_challenge),
        expected_origin=settings.webauthn_origins,
        expected_rp_id=settings.webauthn_rp_id,
    )
    conn.execute(
        "INSERT INTO webauthn_credentials (user_id, credential_id, public_key, sign_count, label) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            user_id,
            bytes_to_base64url(verification.credential_id),
            bytes_to_base64url(verification.credential_public_key),
            verification.sign_count,
            label,
        ),
    )
    conn.commit()


def authentication_options_for_user(conn: sqlite3.Connection, user_id: int) -> str:
    creds = conn.execute(
        "SELECT credential_id FROM webauthn_credentials WHERE user_id = ?", (user_id,)
    ).fetchall()
    options = webauthn.generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(row["credential_id"]))
            for row in creds
        ],
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    store_challenge(conn, user_id, bytes_to_base64url(options.challenge), purpose="authentication")
    return webauthn.options_to_json(options)


def verify_authentication(conn: sqlite3.Connection, user_id: int, credential_json: str) -> bool:
    expected_challenge = consume_challenge(conn, user_id, purpose="authentication")
    if expected_challenge is None:
        return False
    credential = parse_authentication_credential_json(credential_json)
    stored = conn.execute(
        "SELECT id, public_key, sign_count FROM webauthn_credentials "
        "WHERE credential_id = ? AND user_id = ?",
        (bytes_to_base64url(credential.raw_id), user_id),
    ).fetchone()
    if stored is None:
        return False
    verification = webauthn.verify_authentication_response(
        credential=credential,
        expected_challenge=base64url_to_bytes(expected_challenge),
        expected_origin=settings.webauthn_origins,
        expected_rp_id=settings.webauthn_rp_id,
        credential_public_key=base64url_to_bytes(stored["public_key"]),
        credential_current_sign_count=stored["sign_count"],
    )
    conn.execute(
        "UPDATE webauthn_credentials SET sign_count = ? WHERE id = ?",
        (verification.new_sign_count, stored["id"]),
    )
    conn.commit()
    return True
