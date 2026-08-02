"""Parametrised CRUD over the users table. No SQL string interpolation."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from db import _split_full_name

LOCKOUT_MAX_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def is_locked_out(user: dict) -> bool:
    """True if the account is currently within its lockout window."""
    locked_until = user.get("locked_until")
    if not locked_until:
        return False
    try:
        until = datetime.fromisoformat(locked_until)
    except ValueError:
        return False
    if until.tzinfo is None:
        until = until.replace(tzinfo=UTC)
    return datetime.now(UTC) < until


def register_failed_login(conn: sqlite3.Connection, user_id: int) -> dict:
    """Increment the failed-attempt counter; lock the account if the threshold is hit."""
    conn.execute(
        "UPDATE users SET failed_login_attempts = failed_login_attempts + 1 WHERE id = ?",
        (user_id,),
    )
    row = conn.execute(
        "SELECT failed_login_attempts FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if row["failed_login_attempts"] >= LOCKOUT_MAX_ATTEMPTS:
        locked_until = (datetime.now(UTC) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)).isoformat()
        conn.execute("UPDATE users SET locked_until = ? WHERE id = ?", (locked_until, user_id))
    conn.commit()
    return get_user_by_id(conn, user_id)


def reset_failed_login(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute(
        "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = ?",
        (user_id,),
    )
    conn.commit()


def set_account_disabled(conn: sqlite3.Connection, user_id: int, disabled: bool) -> None:
    """Admin-only action (GL-10.1): block/unblock future logins for this user.

    Does not invalidate any already-issued session JWT — an existing session stays
    valid until its normal TTL expires (jwt_ttl_minutes, default 60m).
    """
    conn.execute(
        "UPDATE users SET account_disabled = ? WHERE id = ?",
        (1 if disabled else 0, user_id),
    )
    conn.commit()


def create_user(
    conn: sqlite3.Connection,
    *,
    email: str,
    name: str,
    password_hash: str,
    tier: str = "free",
    audience: str = "base",
    birth_year: int | None = None,
    country: str | None = None,
) -> dict:
    first_name, last_name = _split_full_name(name)
    cur = conn.execute(
        "INSERT INTO users (email, name, password_hash, tier, audience, birth_year, country, "
        "first_name, last_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            email,
            name,
            password_hash,
            tier,
            audience,
            birth_year,
            country.upper() if country else None,
            first_name,
            last_name,
        ),
    )
    conn.commit()
    return get_user_by_id(conn, cur.lastrowid)


def complete_onboarding(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute(
        "UPDATE users SET onboarding_completed_at = datetime('now') "
        "WHERE id = ? AND onboarding_completed_at IS NULL",
        (user_id,),
    )
    conn.commit()


def get_user_by_email(conn: sqlite3.Connection, email: str) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return _row_to_dict(row)


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_dict(row)


def set_audience(conn: sqlite3.Connection, user_id: int, audience: str, *, locked: bool) -> None:
    conn.execute(
        "UPDATE users SET audience = ?, audience_locked = ? WHERE id = ?",
        (audience, 1 if locked else 0, user_id),
    )
    conn.commit()


def set_display_currency(conn: sqlite3.Connection, user_id: int, currency: str) -> None:
    conn.execute(
        "UPDATE users SET display_currency = ? WHERE id = ?",
        (currency, user_id),
    )
    conn.commit()


def set_show_debts(conn: sqlite3.Connection, user_id: int, show_debts: bool) -> None:
    conn.execute("UPDATE users SET show_debts = ? WHERE id = ?", (1 if show_debts else 0, user_id))
    conn.commit()


def set_name(conn: sqlite3.Connection, user_id: int, first_name: str, last_name: str) -> None:
    full_name = f"{first_name} {last_name}".strip()
    conn.execute(
        "UPDATE users SET first_name = ?, last_name = ?, name = ? WHERE id = ?",
        (first_name, last_name, full_name, user_id),
    )
    conn.commit()


def set_avatar_url(conn: sqlite3.Connection, user_id: int, avatar_url: str) -> None:
    conn.execute("UPDATE users SET avatar_url = ? WHERE id = ?", (avatar_url, user_id))
    conn.commit()


def list_all_users(conn: sqlite3.Connection) -> list[dict]:
    """Return all users as dicts (includes password_hash/totp_secret).

    Callers MUST enforce response_model=UserPublic or equivalent
    field filtering to prevent credential exposure in HTTP responses.
    """
    rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def set_totp_secret(conn: sqlite3.Connection, user_id: int, secret: str) -> None:
    conn.execute(
        "UPDATE users SET totp_secret = ?, totp_enabled = 0 WHERE id = ?", (secret, user_id)
    )
    conn.commit()


def enable_totp(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("UPDATE users SET totp_enabled = 1 WHERE id = ?", (user_id,))
    conn.commit()


def disable_totp(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("UPDATE users SET totp_enabled = 0, totp_secret = NULL WHERE id = ?", (user_id,))
    conn.commit()


def enable_email_otp(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("UPDATE users SET email_otp_enabled = 1 WHERE id = ?", (user_id,))
    conn.commit()


def disable_email_otp(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("UPDATE users SET email_otp_enabled = 0 WHERE id = ?", (user_id,))
    conn.commit()


def enable_webauthn(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("UPDATE users SET webauthn_enabled = 1 WHERE id = ?", (user_id,))
    conn.commit()


def disable_webauthn(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("UPDATE users SET webauthn_enabled = 0 WHERE id = ?", (user_id,))
    conn.execute("DELETE FROM webauthn_credentials WHERE user_id = ?", (user_id,))
    conn.commit()


def has_any_webauthn_credential(conn: sqlite3.Connection, user_id: int) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM webauthn_credentials WHERE user_id = ?", (user_id,)
    ).fetchone()
    return bool(row["n"])


def set_household_id(conn: sqlite3.Connection, user_id: int, household_id: str | None) -> None:
    conn.execute("UPDATE users SET household_id = ? WHERE id = ?", (household_id, user_id))
    conn.commit()


def get_household_members(conn: sqlite3.Connection, household_id: str) -> list[dict]:
    """Return all users (id/email/name only) sharing the given household_id."""
    rows = conn.execute(
        "SELECT id, email, name FROM users WHERE household_id = ? ORDER BY id",
        (household_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_share_preferences(conn: sqlite3.Connection, user_id: int) -> dict[str, bool]:
    """Return {resource_type: shared} for every preference this user has set."""
    rows = conn.execute(
        "SELECT resource_type, shared FROM share_preferences WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {r["resource_type"]: bool(r["shared"]) for r in rows}


def set_share_preference(
    conn: sqlite3.Connection, user_id: int, resource_type: str, shared: bool
) -> None:
    conn.execute(
        "INSERT INTO share_preferences (user_id, resource_type, shared, updated_at) "
        "VALUES (?, ?, ?, datetime('now')) "
        "ON CONFLICT(user_id, resource_type) DO UPDATE SET "
        "shared = excluded.shared, updated_at = excluded.updated_at",
        (user_id, resource_type, 1 if shared else 0),
    )
    conn.commit()


def get_visible_owner_ids(conn: sqlite3.Connection, user_id: int, resource_type: str) -> list[int]:
    """Return [user_id, ...household mates who opted to share this resource_type].

    Fails closed to [user_id] (private-only) if the user has no household.
    """
    user = get_user_by_id(conn, user_id)
    if user is None or not user.get("household_id"):
        return [user_id]
    household_id = user["household_id"]
    rows = conn.execute(
        """
        SELECT u.id FROM users u
        JOIN share_preferences sp ON sp.user_id = u.id
        WHERE u.household_id = ? AND sp.resource_type = ? AND sp.shared = 1
        """,
        (household_id, resource_type),
    ).fetchall()
    shared_ids = {r["id"] for r in rows}
    shared_ids.add(user_id)
    return sorted(shared_ids)
