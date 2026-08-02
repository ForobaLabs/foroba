"""Recovery codes: 10 single-use backup codes per user, hashed at rest (argon2).

Generated once at first MFA enrollment, shown to the user exactly once in plaintext,
regenerable afterwards (regenerating invalidates the old set). A code is consumed
(single-use) at the login-challenge step as a last resort when every enrolled method
is unavailable.
"""

from __future__ import annotations

import secrets
import sqlite3

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()
_CODE_COUNT = 10
_CODE_LENGTH = 10
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no ambiguous chars (0/O, 1/I/L)


def _generate_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LENGTH))


def generate_and_store(conn: sqlite3.Connection, user_id: int) -> list[str]:
    """Generate 10 fresh codes, replacing any existing set. Returns plaintext (show once)."""
    codes = [_generate_code() for _ in range(_CODE_COUNT)]
    conn.execute("DELETE FROM recovery_codes WHERE user_id = ?", (user_id,))
    conn.executemany(
        "INSERT INTO recovery_codes (user_id, code_hash) VALUES (?, ?)",
        [(user_id, _ph.hash(code)) for code in codes],
    )
    conn.commit()
    return codes


def verify_and_consume(conn: sqlite3.Connection, user_id: int, code: str) -> bool:
    """Check `code` against this user's unused recovery codes; consume it on match."""
    rows = conn.execute(
        "SELECT id, code_hash FROM recovery_codes WHERE user_id = ? AND used_at IS NULL",
        (user_id,),
    ).fetchall()
    for row in rows:
        try:
            _ph.verify(row["code_hash"], code)
        except VerifyMismatchError:
            continue
        conn.execute(
            "UPDATE recovery_codes SET used_at = datetime('now') WHERE id = ?", (row["id"],)
        )
        conn.commit()
        return True
    return False


def remaining_count(conn: sqlite3.Connection, user_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM recovery_codes WHERE user_id = ? AND used_at IS NULL",
        (user_id,),
    ).fetchone()
    return row["n"] if row else 0
