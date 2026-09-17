"""Parametrised CRUD over the users table. No SQL string interpolation."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from chat_crypto import safe_decrypt, safe_encrypt
from db import _split_full_name

LOCKOUT_MAX_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def _decrypt_user(d: dict | None) -> dict | None:
    """Decrypt sensitive user fields in-place (migration-safe). Returns d."""
    if d is None:
        return None
    d["totp_secret"] = safe_decrypt(d.get("totp_secret"))
    d["totp_secret_pending"] = safe_decrypt(d.get("totp_secret_pending"))
    return d


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
    require_mfa_enrollment: bool = False,
    email_verified: bool = True,
) -> dict:
    first_name, last_name = _split_full_name(name)
    cur = conn.execute(
        "INSERT INTO users (email, name, password_hash, tier, audience, birth_year, country, "
        "first_name, last_name, mfa_enrollment_pending, email_verified) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            1 if require_mfa_enrollment else 0,
            1 if email_verified else 0,
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
    return _decrypt_user(_row_to_dict(row))


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _decrypt_user(_row_to_dict(row))


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
    return [_decrypt_user(dict(r)) for r in rows]


def get_admin_kpis(conn: sqlite3.Connection) -> dict:
    """Aggregate usage stats for the admin KPIs tab (GL-10.1, foroba#185).

    No raw per-user data browsing — only counts/breakdowns, per the issue's explicit
    "no raw-data browsing" scope constraint.
    """
    total_users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    by_tier = {
        r["tier"]: r["n"]
        for r in conn.execute("SELECT tier, COUNT(*) AS n FROM users GROUP BY tier").fetchall()
    }
    by_audience = {
        r["audience"]: r["n"]
        for r in conn.execute(
            "SELECT audience, COUNT(*) AS n FROM users GROUP BY audience"
        ).fetchall()
    }
    signups_7d = conn.execute(
        "SELECT COUNT(*) AS n FROM users WHERE created_at >= datetime('now', '-7 days')"
    ).fetchone()["n"]
    signups_30d = conn.execute(
        "SELECT COUNT(*) AS n FROM users WHERE created_at >= datetime('now', '-30 days')"
    ).fetchone()["n"]
    mfa_enrolled = conn.execute(
        "SELECT COUNT(*) AS n FROM users WHERE totp_enabled = 1 OR email_otp_enabled = 1 "
        "OR webauthn_enabled = 1"
    ).fetchone()["n"]
    mfa_pending = conn.execute(
        "SELECT COUNT(*) AS n FROM users WHERE mfa_enrollment_pending = 1"
    ).fetchone()["n"]
    disabled = conn.execute(
        "SELECT COUNT(*) AS n FROM users WHERE account_disabled = 1"
    ).fetchone()["n"]
    admins = conn.execute("SELECT COUNT(*) AS n FROM users WHERE is_admin = 1").fetchone()["n"]
    return {
        "total_users": total_users,
        "users_by_tier": by_tier,
        "users_by_audience": by_audience,
        "signups_last_7d": signups_7d,
        "signups_last_30d": signups_30d,
        "mfa_enrolled": mfa_enrolled,
        "mfa_enrollment_pending": mfa_pending,
        "accounts_disabled": disabled,
        "admins": admins,
    }


def create_invite_code(
    conn: sqlite3.Connection,
    *,
    code: str,
    note: str | None,
    max_uses: int,
    expires_at: str | None,
    created_by_user_id: int,
) -> dict:
    cur = conn.execute(
        "INSERT INTO invite_codes (code, note, max_uses, expires_at, created_by_user_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (code, note, max_uses, expires_at, created_by_user_id),
    )
    conn.commit()
    return _row_to_dict(
        conn.execute("SELECT * FROM invite_codes WHERE id = ?", (cur.lastrowid,)).fetchone()
    )


def list_invite_codes(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM invite_codes ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def revoke_invite_code(conn: sqlite3.Connection, code_id: int) -> bool:
    cur = conn.execute(
        "UPDATE invite_codes SET revoked_at = datetime('now') "
        "WHERE id = ? AND revoked_at IS NULL",
        (code_id,),
    )
    conn.commit()
    return cur.rowcount > 0


def redeem_invite_code(conn: sqlite3.Connection, code: str) -> bool:
    """Atomically validate + consume a code. Returns False if invalid/exhausted/expired."""
    cur = conn.execute(
        "UPDATE invite_codes SET uses_count = uses_count + 1 "
        "WHERE code = ? AND revoked_at IS NULL AND uses_count < max_uses "
        "AND (expires_at IS NULL OR expires_at > datetime('now'))",
        (code,),
    )
    conn.commit()
    return cur.rowcount > 0


def set_totp_secret(conn: sqlite3.Connection, user_id: int, secret: str) -> None:
    """Stage a freshly generated TOTP secret without touching the live totp_secret or
    totp_enabled columns (FOR-D06) — only enable_totp() promotes it, on a successful verify."""
    conn.execute(
        "UPDATE users SET totp_secret_pending = ? WHERE id = ?",
        (safe_encrypt(secret), user_id),
    )
    conn.commit()


def enable_totp(conn: sqlite3.Connection, user_id: int) -> None:
    """Atomically promote the pending secret (if any) to the live totp_secret column and
    enable MFA. Uses COALESCE so a caller that set totp_secret directly (e.g. legacy
    fixtures/tests) still works even with no pending value staged."""
    conn.execute(
        "UPDATE users SET"
        " totp_secret = COALESCE(totp_secret_pending, totp_secret),"
        " totp_secret_pending = NULL,"
        " totp_enabled = 1,"
        " mfa_enrollment_pending = 0"
        " WHERE id = ?",
        (user_id,),
    )
    conn.commit()


def disable_totp(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute(
        "UPDATE users SET totp_enabled = 0, totp_secret = NULL, totp_secret_pending = NULL"
        " WHERE id = ?",
        (user_id,),
    )
    conn.commit()


def enable_email_otp(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute(
        "UPDATE users SET email_otp_enabled = 1, mfa_enrollment_pending = 0 WHERE id = ?",
        (user_id,),
    )
    conn.commit()


def disable_email_otp(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("UPDATE users SET email_otp_enabled = 0 WHERE id = ?", (user_id,))
    conn.commit()


def enable_webauthn(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute(
        "UPDATE users SET webauthn_enabled = 1, mfa_enrollment_pending = 0 WHERE id = ?",
        (user_id,),
    )
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


def record_consent(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    document_type: str,
    document_version: str,
    ip_address: str | None,
) -> None:
    conn.execute(
        "INSERT INTO consents (user_id, document_type, document_version, ip_address) "
        "VALUES (?, ?, ?, ?)",
        (user_id, document_type, document_version, ip_address),
    )
    conn.commit()


def latest_consent_versions(conn: sqlite3.Connection, user_id: int) -> dict[str, str]:
    """Return {document_type: most-recently-accepted version} for a user."""
    rows = conn.execute(
        "SELECT document_type, document_version FROM consents "
        "WHERE user_id = ? ORDER BY accepted_at ASC",
        (user_id,),
    ).fetchall()
    latest: dict[str, str] = {}
    for row in rows:
        latest[row["document_type"]] = row["document_version"]  # ascending => last write wins
    return latest


def get_consents(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT document_type, document_version, accepted_at FROM consents "
        "WHERE user_id = ? ORDER BY accepted_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def update_processing_prefs(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    processing_restricted: bool | None,
    marketing_objection: bool | None,
) -> None:
    """CL-2.2 — set GDPR art.18/21 flags for a user."""
    if processing_restricted is not None:
        conn.execute(
            "UPDATE users SET processing_restricted = ? WHERE id = ?",
            (int(processing_restricted), user_id),
        )
    if marketing_objection is not None:
        conn.execute(
            "UPDATE users SET marketing_objection = ? WHERE id = ?",
            (int(marketing_objection), user_id),
        )


def delete_user(conn: sqlite3.Connection, user_id: int) -> None:
    """foroba#183 — GDPR Art. 17 erasure: hard-delete every row this app holds for
    user_id. fx_rates is excluded — it's global/shared cached reference data, not
    personal data. household_id is just a shared string other members' own rows
    keep independently, so deleting this user's own row needs no extra cleanup on
    their side (mirrors what /auth/household/leave already does for that user)."""
    webhook_ids = [
        row[0]
        for row in conn.execute("SELECT id FROM webhooks WHERE user_id = ?", (user_id,)).fetchall()
    ]
    if webhook_ids:
        placeholders = ", ".join("?" * len(webhook_ids))
        conn.execute(
            f"DELETE FROM webhook_deliveries WHERE webhook_id IN ({placeholders})", webhook_ids
        )
    conn.execute("DELETE FROM webhooks WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM api_keys WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM monthly_reports WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM whatif_scenarios WHERE created_by_user_id = ?", (user_id,))
    conn.execute("DELETE FROM recurring_amount_baselines WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM notification_dismissals WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM sandbox_user_context WHERE user_id = ?", (str(user_id),))
    conn.execute("DELETE FROM sandbox_conversations WHERE user_id = ?", (str(user_id),))
    conn.execute("DELETE FROM consents WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM webauthn_challenges WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM webauthn_credentials WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM email_otp_codes WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM recovery_codes WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM share_preferences WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()


def set_email_verified(conn: sqlite3.Connection, user_id: int, verified: bool = True) -> None:
    """A2 (foroba#178) — mark the user's email address as verified."""
    conn.execute(
        "UPDATE users SET email_verified = ? WHERE id = ?",
        (1 if verified else 0, user_id),
    )
    conn.commit()


def set_pending_email(
    conn: sqlite3.Connection, user_id: int, pending_email: str | None
) -> None:
    """A6 (foroba#182) — store or clear the pending new email address."""
    conn.execute("UPDATE users SET pending_email = ? WHERE id = ?", (pending_email, user_id))
    conn.commit()


def apply_pending_email(conn: sqlite3.Connection, user_id: int) -> str | None:
    """Apply pending_email → email and clear it. Returns the new email or None."""
    user = get_user_by_id(conn, user_id)
    if not user or not user.get("pending_email"):
        return None
    new_email = user["pending_email"]
    conn.execute(
        "UPDATE users SET email = ?, pending_email = NULL WHERE id = ?",
        (new_email, user_id),
    )
    conn.commit()
    return new_email


def create_household_invite(
    conn: sqlite3.Connection,
    *,
    inviter_id: int,
    household_id: str,
    invited_email: str,
    token_hash: str,
    expires_at: str,
) -> dict:
    """A4 (foroba#180) — insert a household invite record."""
    cur = conn.execute(
        "INSERT INTO household_invites "
        "(inviter_id, household_id, invited_email, token_hash, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (inviter_id, household_id, invited_email, token_hash, expires_at),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM household_invites WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    return dict(row)


def get_household_invite_by_token_hash(
    conn: sqlite3.Connection, token_hash: str
) -> dict | None:
    row = conn.execute(
        "SELECT * FROM household_invites WHERE token_hash = ?", (token_hash,)
    ).fetchone()
    return dict(row) if row else None


def accept_household_invite(conn: sqlite3.Connection, invite_id: int) -> None:
    conn.execute(
        "UPDATE household_invites SET accepted_at = datetime('now') WHERE id = ?",
        (invite_id,),
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
