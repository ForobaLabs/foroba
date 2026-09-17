"""Tests for email verification, email change, and household invite flows
(foroba#178, foroba#182, foroba#180, foroba#184).
"""

from __future__ import annotations

import smtplib
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import email_service
from auth.conn import get_conn
from auth.router import router as auth_router
from config import settings
from db import init_schema
from rate_limit import limiter
from settings_store import init_settings

# ---------------------------------------------------------------------------
# Shared SMTP stub
# ---------------------------------------------------------------------------

class FakeSMTP:
    instances: ClassVar[list[FakeSMTP]] = []

    def __init__(self, host, port, timeout=10):
        self.host = host
        self.sent: list[tuple] = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def sendmail(self, from_addr, to_addrs, msg):
        self.sent.append((from_addr, to_addrs, msg))


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    FakeSMTP.instances.clear()
    limiter.reset()
    # Enable SMTP by default for these tests
    settings.smtp_enabled = True
    settings.smtp_host = "smtp.test.local"
    settings.smtp_port = 587
    settings.smtp_user = "bot@test.local"
    settings.smtp_password = "secret"
    settings.smtp_from = "noreply@foroba.app"
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    yield
    FakeSMTP.instances.clear()
    limiter.reset()
    settings.smtp_enabled = False


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    init_schema(c)
    init_settings(c)
    return c


@pytest.fixture
def client(conn):
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(auth_router)
    return TestClient(app, raise_server_exceptions=False)


def _register(client, email="alice@example.com"):
    r = client.post(
        "/auth/register",
        json={
            "email": email,
            "email_confirm": email,
            "name": "Alice Test",
            "password": "Secret1234!",
            "password_confirm": "Secret1234!",
            "tos_accepted": True,
        },
    )
    assert r.status_code == 201, r.text
    return r


def _get_latest_otp(conn, user_id: int) -> str:
    """Extract the raw OTP code stored in email_otp_codes (by brute-force check)."""
    # Use the email_otp module's generate function directly, then pull the hash
    # and verify against known codes — not practical. Instead, peek at what was sent.
    # The FakeSMTP captures the full MIME message; we extract the 6-digit code.
    import re
    for smtp in reversed(FakeSMTP.instances):
        for _, _, msg in reversed(smtp.sent):
            m = re.search(r"\b(\d{6})\b", msg)
            if m:
                return m.group(1)
    raise RuntimeError("No OTP found in sent emails")


# ---------------------------------------------------------------------------
# #184 — email_service template functions
# ---------------------------------------------------------------------------

def _decoded_parts(msg: str) -> list[str]:
    """Non-ASCII (accented FR/IT) template text makes Python's email module
    base64-encode the multipart/alternative parts, so the raw MIME string no
    longer contains the plain code/text verbatim -- decode each part first."""
    import email

    parsed = email.message_from_string(msg)
    return [
        part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
        for part in parsed.walk()
        if part.get_content_maintype() != "multipart"
    ]


class TestEmailTemplates:
    def test_send_otp_email_sends_html(self):
        email_service.send_otp_email("u@example.com", "123456", country="FR")
        assert FakeSMTP.instances
        _, _, msg = FakeSMTP.instances[0].sent[0]
        parts = _decoded_parts(msg)
        assert any("123456" in part for part in parts)
        assert "text/html" in msg

    def test_send_signup_verify_email(self):
        email_service.send_signup_verify_email("u@example.com", "654321", country="IT")
        _, _, msg = FakeSMTP.instances[0].sent[0]
        parts = _decoded_parts(msg)
        assert any("654321" in part for part in parts)
        # Italian translation should be present
        assert any("Foroba" in part for part in parts)

    def test_send_email_change_email(self):
        email_service.send_email_change_email("new@example.com", "111222")
        _, _, msg = FakeSMTP.instances[0].sent[0]
        assert "111222" in msg

    def test_send_household_invite_email(self):
        email_service.send_household_invite_email(
            "friend@example.com", "ABCDEF12", inviter_name="Bob"
        )
        _, _, msg = FakeSMTP.instances[0].sent[0]
        assert "ABCDEF12" in msg
        assert "Bob" in msg

    def test_disabled_smtp_does_not_send(self):
        settings.smtp_enabled = False
        email_service.send_otp_email("u@example.com", "999999")
        assert FakeSMTP.instances == []

    def test_lang_detection(self):
        assert email_service._lang("FR") == "fr"
        assert email_service._lang("BE") == "fr"
        assert email_service._lang("IT") == "it"
        assert email_service._lang("DE") == "en"
        assert email_service._lang(None) == "en"


# ---------------------------------------------------------------------------
# #178 — email verification at signup
# ---------------------------------------------------------------------------

class TestEmailVerify:
    def test_register_smtp_enabled_creates_unverified_user(self, client, conn):
        r = _register(client)
        user_id = r.json()["id"]
        row = conn.execute(
            "SELECT email_verified FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        assert row["email_verified"] == 0

    def test_register_smtp_enabled_sends_welcome_email(self, client):
        _register(client)
        assert FakeSMTP.instances, "Should have sent a verification email"
        _, to_addrs, msg = FakeSMTP.instances[0].sent[0]
        assert "alice@example.com" in to_addrs[0]
        # 6-digit code should appear in the message
        import re
        assert re.search(r"\b\d{6}\b", msg)

    def test_register_smtp_disabled_creates_verified_user(self, client, conn):
        settings.smtp_enabled = False
        r = _register(client)
        user_id = r.json()["id"]
        row = conn.execute(
            "SELECT email_verified FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        assert row["email_verified"] == 1

    def test_verify_email_sets_verified(self, client, conn):
        r = _register(client)
        user_id = r.json()["id"]
        # Inject a known OTP directly
        from argon2 import PasswordHasher
        ph = PasswordHasher()
        expires_at = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
        conn.execute(
            "INSERT INTO email_otp_codes (user_id, code_hash, expires_at) VALUES (?, ?, ?)",
            (user_id, ph.hash("123456"), expires_at),
        )
        conn.commit()
        resp = client.post("/auth/verify-email", json={"code": "123456"})
        assert resp.status_code == 204, resp.text
        row = conn.execute(
            "SELECT email_verified FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        assert row["email_verified"] == 1

    def test_verify_email_wrong_code(self, client, conn):
        r = _register(client)
        user_id = r.json()["id"]
        from argon2 import PasswordHasher
        ph = PasswordHasher()
        expires_at = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
        conn.execute(
            "INSERT INTO email_otp_codes (user_id, code_hash, expires_at) VALUES (?, ?, ?)",
            (user_id, ph.hash("123456"), expires_at),
        )
        conn.commit()
        resp = client.post("/auth/verify-email", json={"code": "000000"})
        assert resp.status_code == 400

    def test_verify_email_already_verified_is_idempotent(self, client, conn):
        settings.smtp_enabled = False
        _register(client)
        # Already verified — should return 204 silently
        resp = client.post("/auth/verify-email", json={"code": "000000"})
        assert resp.status_code == 204

    def test_resend_verification_requires_auth(self, client):
        resp = TestClient(client.app).post("/auth/resend-verification")
        assert resp.status_code in (401, 403)

    def test_resend_verification_sends_email(self, client, conn):
        _register(client)
        FakeSMTP.instances.clear()
        resp = client.post("/auth/resend-verification")
        assert resp.status_code == 204
        assert FakeSMTP.instances, "Resend should have sent an email"

    def test_resend_verification_already_verified_is_noop(self, client, conn):
        settings.smtp_enabled = False
        _register(client)
        settings.smtp_enabled = True
        FakeSMTP.instances.clear()
        resp = client.post("/auth/resend-verification")
        assert resp.status_code == 204
        assert FakeSMTP.instances == []  # no email — already verified


# ---------------------------------------------------------------------------
# #182 — email change flow
# ---------------------------------------------------------------------------

class TestEmailChange:
    def _verified_client(self, client, conn):
        """Register + mark email_verified=1."""
        r = _register(client)
        user_id = r.json()["id"]
        conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (user_id,))
        conn.commit()
        return user_id

    def test_change_request_sends_otp_to_new_email(self, client, conn):
        self._verified_client(client, conn)
        FakeSMTP.instances.clear()
        resp = client.post(
            "/auth/me/email/change-request",
            json={
                "new_email": "new_alice@example.com",
                "new_email_confirm": "new_alice@example.com",
            },
        )
        assert resp.status_code == 204, resp.text
        assert FakeSMTP.instances
        _, to_addrs, _ = FakeSMTP.instances[0].sent[0]
        assert "new_alice@example.com" in to_addrs[0]

    def test_change_request_stores_pending_email(self, client, conn):
        user_id = self._verified_client(client, conn)
        client.post(
            "/auth/me/email/change-request",
            json={
                "new_email": "new_alice@example.com",
                "new_email_confirm": "new_alice@example.com",
            },
        )
        row = conn.execute(
            "SELECT pending_email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        assert row["pending_email"] == "new_alice@example.com"

    def test_change_confirm_applies_new_email(self, client, conn):
        user_id = self._verified_client(client, conn)
        client.post(
            "/auth/me/email/change-request",
            json={
                "new_email": "new_alice@example.com",
                "new_email_confirm": "new_alice@example.com",
            },
        )
        # Inject a known OTP
        from argon2 import PasswordHasher
        ph = PasswordHasher()
        expires_at = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
        conn.execute(
            "INSERT INTO email_otp_codes (user_id, code_hash, expires_at) VALUES (?, ?, ?)",
            (user_id, ph.hash("777888"), expires_at),
        )
        conn.commit()
        resp = client.post("/auth/me/email/change-confirm", json={"code": "777888"})
        assert resp.status_code == 204, resp.text
        row = conn.execute(
            "SELECT email, pending_email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        assert row["email"] == "new_alice@example.com"
        assert row["pending_email"] is None

    def test_change_confirm_wrong_code(self, client, conn):
        user_id = self._verified_client(client, conn)
        conn.execute("UPDATE users SET pending_email = 'x@example.com' WHERE id = ?", (user_id,))
        conn.commit()
        resp = client.post("/auth/me/email/change-confirm", json={"code": "000000"})
        assert resp.status_code == 400

    def test_change_confirm_no_pending_email(self, client, conn):
        self._verified_client(client, conn)
        resp = client.post("/auth/me/email/change-confirm", json={"code": "123456"})
        assert resp.status_code == 400

    def test_change_request_unverified_user_blocked(self, client, conn):
        # email_verified=0 (SMTP enabled at registration)
        _register(client)
        resp = client.post(
            "/auth/me/email/change-request",
            json={
                "new_email": "other@example.com",
                "new_email_confirm": "other@example.com",
            },
        )
        assert resp.status_code == 403

    def test_change_request_duplicate_email(self, client, conn):
        self._verified_client(client, conn)
        # Register second user
        settings.smtp_enabled = False
        _register(client, "bob@example.com")
        settings.smtp_enabled = True
        resp = client.post(
            "/auth/me/email/change-request",
            json={
                "new_email": "bob@example.com",
                "new_email_confirm": "bob@example.com",
            },
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# #180 — household invite by email
# ---------------------------------------------------------------------------

class TestHouseholdInvite:
    def _verified_client(self, client, conn, email="alice@example.com"):
        r = _register(client, email)
        user_id = r.json()["id"]
        conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (user_id,))
        conn.commit()
        return user_id

    def test_invite_sends_email(self, client, conn):
        self._verified_client(client, conn)
        FakeSMTP.instances.clear()
        resp = client.post("/auth/household/invite", json={"email": "friend@example.com"})
        assert resp.status_code == 204, resp.text
        assert FakeSMTP.instances
        _, to_addrs, _ = FakeSMTP.instances[0].sent[0]
        assert "friend@example.com" in to_addrs[0]

    def test_invite_stores_record(self, client, conn):
        user_id = self._verified_client(client, conn)
        client.post("/auth/household/invite", json={"email": "friend@example.com"})
        row = conn.execute(
            "SELECT * FROM household_invites WHERE invited_email = 'friend@example.com'"
        ).fetchone()
        assert row is not None
        assert row["inviter_id"] == user_id
        assert row["accepted_at"] is None

    def test_invite_self_rejected(self, client, conn):
        self._verified_client(client, conn)
        resp = client.post("/auth/household/invite", json={"email": "alice@example.com"})
        assert resp.status_code == 400

    def test_invite_accept_joins_household(self, client, conn):
        self._verified_client(client, conn, "alice@example.com")
        # Register the invitee on a separate client -- registering on the
        # shared `client` would overwrite Alice's session cookie with Bob's
        # (register() always sets a fresh session cookie on success), making
        # the invite call below run as Bob instead of Alice.
        bob_register_client = TestClient(client.app)
        settings.smtp_enabled = False
        _register(bob_register_client, "bob@example.com")
        settings.smtp_enabled = True
        bob_id = conn.execute(
            "SELECT id FROM users WHERE email = 'bob@example.com'"
        ).fetchone()["id"]
        conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (bob_id,))
        conn.commit()

        # Alice sends invite
        FakeSMTP.instances.clear()
        client.post("/auth/household/invite", json={"email": "bob@example.com"})
        # Extract token from sent email
        import re
        _, _, msg = FakeSMTP.instances[0].sent[0]
        token = re.search(r"\b([A-F0-9]{12})\b", msg)
        assert token, f"No token found in: {msg[:200]}"
        token_str = token.group(1)

        # Bob logs in and accepts
        bob_client = TestClient(client.app)
        bob_client.post(
            "/auth/login",
            json={"email": "bob@example.com", "password": "Secret1234!"},
        )
        resp = bob_client.post("/auth/household/invite/accept", json={"token": token_str})
        assert resp.status_code == 204, resp.text

        # Bob should now have a household_id
        bob_row = conn.execute("SELECT household_id FROM users WHERE id = ?", (bob_id,)).fetchone()
        assert bob_row["household_id"] is not None

    def test_invite_accept_wrong_token(self, client, conn):
        self._verified_client(client, conn)
        resp = client.post("/auth/household/invite/accept", json={"token": "ZZZZZZZZZZZZ"})
        assert resp.status_code == 404

    def test_invite_smtp_disabled_returns_503(self, client, conn):
        self._verified_client(client, conn)
        settings.smtp_enabled = False
        resp = client.post("/auth/household/invite", json={"email": "x@example.com"})
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# FOR-D04 — household join must require the target's consent, and leaving
# a household must not let stale sharing opt-ins carry over to the next one.
# ---------------------------------------------------------------------------

class TestHouseholdJoinConsent:
    def _verified_client(self, client, conn, email="alice@example.com"):
        r = _register(client, email)
        user_id = r.json()["id"]
        conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (user_id,))
        conn.commit()
        return user_id

    def test_household_join_requires_target_consent(self, client, conn):
        """/household/join must no longer merge household_id unilaterally --
        it must only send a consent-requiring invite, exactly like
        /household/invite. No merge should happen until the target calls
        /household/invite/accept."""
        alice_id = self._verified_client(client, conn, "alice@example.com")

        bob_register_client = TestClient(client.app)
        settings.smtp_enabled = False
        bob_id = _register(bob_register_client, "bob@example.com").json()["id"]
        settings.smtp_enabled = True
        conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (bob_id,))
        conn.commit()

        FakeSMTP.instances.clear()
        resp = client.post("/auth/household/join", json={"email": "bob@example.com"})
        assert resp.status_code == 204, resp.text

        # No unilateral merge -- neither party has a household_id yet.
        alice_row = conn.execute(
            "SELECT household_id FROM users WHERE id = ?", (alice_id,)
        ).fetchone()
        bob_row = conn.execute(
            "SELECT household_id FROM users WHERE id = ?", (bob_id,)
        ).fetchone()
        assert alice_row["household_id"] is not None, "inviter gets a pending household_id"
        assert bob_row["household_id"] is None, "target must not be merged before consenting"

        # A real invite record was created for Bob, and he must accept it.
        assert FakeSMTP.instances
        import re
        _, to_addrs, msg = FakeSMTP.instances[0].sent[0]
        assert "bob@example.com" in to_addrs[0]
        token = re.search(r"\b([A-F0-9]{12})\b", msg)
        assert token, f"No token found in: {msg[:200]}"

        bob_client = TestClient(client.app)
        bob_client.post(
            "/auth/login", json={"email": "bob@example.com", "password": "Secret1234!"}
        )
        accept_resp = bob_client.post(
            "/auth/household/invite/accept", json={"token": token.group(1)}
        )
        assert accept_resp.status_code == 204, accept_resp.text

        bob_row_after = conn.execute(
            "SELECT household_id FROM users WHERE id = ?", (bob_id,)
        ).fetchone()
        assert bob_row_after["household_id"] == alice_row["household_id"]

    def test_household_join_self_rejected(self, client, conn):
        self._verified_client(client, conn, "alice@example.com")
        resp = client.post("/auth/household/join", json={"email": "alice@example.com"})
        assert resp.status_code == 400

    def test_household_leave_clears_share_preferences_for_that_household(self, client, conn):
        """A stale sharing opt-in must not silently apply to whichever new
        household the user joins next -- leaving must clear it."""
        alice_id = self._verified_client(client, conn, "alice@example.com")
        conn.execute(
            "UPDATE users SET household_id = 'household-1' WHERE id = ?", (alice_id,)
        )
        conn.commit()
        resp = client.put(
            "/auth/household/share", json={"resource_type": "networth", "shared": True}
        )
        assert resp.status_code == 204, resp.text
        prefs = conn.execute(
            "SELECT shared FROM share_preferences WHERE user_id = ? AND resource_type = 'networth'",
            (alice_id,),
        ).fetchone()
        assert prefs is not None and prefs["shared"] == 1

        resp = client.post("/auth/household/leave")
        assert resp.status_code == 204, resp.text

        prefs_after = conn.execute(
            "SELECT shared FROM share_preferences WHERE user_id = ? AND resource_type = 'networth'",
            (alice_id,),
        ).fetchone()
        assert prefs_after is None, "share_preferences must be cleared on leave"

        household_row = conn.execute(
            "SELECT household_id FROM users WHERE id = ?", (alice_id,)
        ).fetchone()
        assert household_row["household_id"] is None
