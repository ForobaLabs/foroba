"""Email OTP: 6-digit codes sent via the existing SMTP wiring (email_service.send_email),
hashed at rest (argon2), 30-minute expiry, single-use. Issuing a code voids any older
unused one, and _MAX_FAILED_ATTEMPTS wrong guesses void the outstanding code, so a
6-digit code cannot be brute-forced within its lifetime (pre-beta Task 2.2).
"""

from __future__ import annotations

import secrets
import sqlite3
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from config import settings
from email_service import send_otp_email, send_signup_verify_email

_ph = PasswordHasher()
_CODE_TTL_MINUTES = 30
_MAX_FAILED_ATTEMPTS = 5


class EmailNotConfiguredError(RuntimeError):
    """Raised when email OTP is requested but SMTP is not enabled/configured."""


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _store_code(conn: sqlite3.Connection, user_id: int) -> str:
    """Void the user's outstanding codes, then store and return a fresh one."""
    code = _generate_code()
    expires_at = (datetime.now(UTC) + timedelta(minutes=_CODE_TTL_MINUTES)).isoformat()
    conn.execute(
        "UPDATE email_otp_codes SET used_at = datetime('now') "
        "WHERE user_id = ? AND used_at IS NULL",
        (user_id,),
    )
    conn.execute(
        "INSERT INTO email_otp_codes (user_id, code_hash, expires_at) VALUES (?, ?, ?)",
        (user_id, _ph.hash(code), expires_at),
    )
    conn.commit()
    return code


def generate_and_send(
    conn: sqlite3.Connection,
    user_id: int,
    email: str,
    *,
    country: str | None = None,
) -> None:
    """Generate a fresh 6-digit code, store its hash, and email it. Raises if SMTP is off —
    the caller must surface this as an error, never silently pretend a code was sent."""
    if not settings.smtp_enabled:
        raise EmailNotConfiguredError("Email OTP requires SMTP to be configured")
    code = _store_code(conn, user_id)
    send_otp_email(email, code, country=country, ttl_minutes=_CODE_TTL_MINUTES)


def generate_and_send_signup_verify(
    conn: sqlite3.Connection,
    user_id: int,
    email: str,
    *,
    country: str | None = None,
) -> None:
    """Like generate_and_send but uses the signup-welcome template (A2, foroba#178)."""
    if not settings.smtp_enabled:
        raise EmailNotConfiguredError("Email OTP requires SMTP to be configured")
    code = _store_code(conn, user_id)
    send_signup_verify_email(email, code, country=country, ttl_minutes=_CODE_TTL_MINUTES)


def verify_and_consume(conn: sqlite3.Connection, user_id: int, code: str) -> bool:
    now = datetime.now(UTC).isoformat()
    rows = conn.execute(
        """
        SELECT id, code_hash, failed_attempts FROM email_otp_codes
        WHERE user_id = ? AND used_at IS NULL AND expires_at > ?
        ORDER BY id DESC
        """,
        (user_id, now),
    ).fetchall()
    for row in rows:
        try:
            _ph.verify(row["code_hash"], code)
        except VerifyMismatchError:
            continue
        conn.execute(
            "UPDATE email_otp_codes SET used_at = datetime('now') WHERE id = ?", (row["id"],)
        )
        conn.commit()
        return True
    if rows:
        conn.execute(
            "UPDATE email_otp_codes SET failed_attempts = failed_attempts + 1, "
            "used_at = CASE WHEN failed_attempts + 1 >= ? THEN datetime('now') END "
            "WHERE user_id = ? AND used_at IS NULL",
            (_MAX_FAILED_ATTEMPTS, user_id),
        )
        conn.commit()
    return False
