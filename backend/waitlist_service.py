"""Public-site waitlist (Plan D, S1) — double opt-in, token stored only as SHA-256.

Pure service: no FastAPI imports, so it is unit-testable with an in-memory connection.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3

ALLOWED_APPS: frozenset[str] = frozenset({"naforo", "yiriba", "kelen"})
ALLOWED_LANGS: frozenset[str] = frozenset({"en", "it", "fr"})
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MAX_EMAIL = 254


class WaitlistError(ValueError):
    """Invalid waitlist input; the message is a stable machine-readable code."""


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _normalise(email: str, apps: list[str], lang: str, consent: bool) -> tuple[str, str, str]:
    clean = (email or "").strip().lower()
    if len(clean) > _MAX_EMAIL or not _EMAIL_RE.match(clean):
        raise WaitlistError("invalid_email")
    if any(a not in ALLOWED_APPS for a in apps):
        raise WaitlistError("invalid_apps")
    if not consent:
        raise WaitlistError("consent_required")
    return clean, ",".join(sorted(set(apps))), lang if lang in ALLOWED_LANGS else "en"


def join(
    conn: sqlite3.Connection, *, email: str, apps: list[str], lang: str, consent: bool
) -> str | None:
    """Insert or refresh a pending sign-up. Returns the plaintext token to email, or None
    if the address is already confirmed (caller answers identically either way)."""
    clean, app_csv, lang = _normalise(email, apps, lang, consent)
    row = conn.execute("SELECT confirmed_at FROM waitlist WHERE email = ?", (clean,)).fetchone()
    if row and row[0]:
        return None
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO waitlist (email, apps, lang, consent_at, confirm_token_hash) "
        "VALUES (?, ?, ?, datetime('now'), ?) "
        "ON CONFLICT(email) DO UPDATE SET apps = excluded.apps, lang = excluded.lang, "
        "consent_at = excluded.consent_at, confirm_token_hash = excluded.confirm_token_hash",
        (clean, app_csv, lang, hash_token(token)),
    )
    conn.commit()
    return token


def confirm(conn: sqlite3.Connection, token: str) -> bool:
    """Mark the sign-up owning `token` as confirmed. Single use."""
    cur = conn.execute(
        "UPDATE waitlist SET confirmed_at = datetime('now'), confirm_token_hash = NULL "
        "WHERE confirm_token_hash = ? AND confirmed_at IS NULL",
        (hash_token(token or ""),),
    )
    conn.commit()
    return cur.rowcount == 1
