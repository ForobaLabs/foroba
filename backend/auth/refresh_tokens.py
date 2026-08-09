"""Opaque, rotating refresh tokens for cookieless clients (iOS, self-host CLI).

Tokens are 32 random bytes, urlsafe-base64 encoded, handed to the client once and
never stored in plaintext -- only a SHA-256 hash is persisted. Every use rotates the
token; presenting an already-rotated token is treated as theft and revokes the whole
family (RFC 6819 section 5.2.2.3 refresh-token reuse detection).
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta

from config import settings


class InvalidRefreshToken(Exception):
    """The token is unknown, malformed, or expired."""


class ReuseDetected(Exception):
    """An already-rotated token was presented -- the family has been revoked."""


def _hash(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def issue(
    conn: sqlite3.Connection,
    user_id: int,
    device_label: str | None,
    *,
    family_id: str | None = None,
) -> str:
    plaintext = secrets.token_urlsafe(32)
    expires_at = (
        datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days)
    ).isoformat()
    conn.execute(
        "INSERT INTO refresh_tokens "
        "(user_id, token_hash, family_id, device_label, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            user_id,
            _hash(plaintext),
            family_id or str(uuid.uuid4()),
            device_label,
            _now(),
            expires_at,
        ),
    )
    conn.commit()
    return plaintext


def _revoke_family(conn: sqlite3.Connection, family_id: str) -> None:
    conn.execute(
        "UPDATE refresh_tokens SET revoked_at = ? "
        "WHERE family_id = ? AND revoked_at IS NULL",
        (_now(), family_id),
    )
    conn.commit()


def rotate(conn: sqlite3.Connection, plaintext: str) -> tuple[str, dict]:
    row = conn.execute(
        "SELECT * FROM refresh_tokens WHERE token_hash = ?",
        (_hash(plaintext),),
    ).fetchone()
    if row is None:
        raise InvalidRefreshToken("unknown refresh token")
    row = dict(row)
    if row["revoked_at"] is not None:
        # Distinguish: was this token rotated out (successor exists in family)?
        # If yes → replay of an old token → revoke family + ReuseDetected.
        # If no  → token revoked by a prior security action → just InvalidRefreshToken.
        successor_exists = conn.execute(
            "SELECT 1 FROM refresh_tokens "
            "WHERE family_id = ? AND id > ? LIMIT 1",
            (row["family_id"], row["id"]),
        ).fetchone()
        if successor_exists:
            _revoke_family(conn, row["family_id"])
            raise ReuseDetected("refresh token replay detected; family revoked")
        raise InvalidRefreshToken("refresh token has been revoked")
    if datetime.fromisoformat(row["expires_at"]) <= datetime.now(UTC):
        raise InvalidRefreshToken("expired refresh token")
    conn.execute(
        "UPDATE refresh_tokens SET revoked_at = ?, last_used_at = ? WHERE id = ?",
        (_now(), _now(), row["id"]),
    )
    conn.commit()
    new_plaintext = issue(
        conn, row["user_id"], row["device_label"], family_id=row["family_id"]
    )
    return new_plaintext, row


def revoke(conn: sqlite3.Connection, plaintext: str) -> None:
    conn.execute(
        "UPDATE refresh_tokens SET revoked_at = ? "
        "WHERE token_hash = ? AND revoked_at IS NULL",
        (_now(), _hash(plaintext)),
    )
    conn.commit()


def revoke_all_for_user(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute(
        "UPDATE refresh_tokens SET revoked_at = ? "
        "WHERE user_id = ? AND revoked_at IS NULL",
        (_now(), user_id),
    )
    conn.commit()


def list_sessions(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, device_label, created_at, last_used_at, expires_at "
        "FROM refresh_tokens WHERE user_id = ? AND revoked_at IS NULL "
        "ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def revoke_session(conn: sqlite3.Connection, user_id: int, session_id: int) -> bool:
    cur = conn.execute(
        "UPDATE refresh_tokens SET revoked_at = ? "
        "WHERE id = ? AND user_id = ? AND revoked_at IS NULL",
        (_now(), session_id, user_id),
    )
    conn.commit()
    return cur.rowcount > 0
