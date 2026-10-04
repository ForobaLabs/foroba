"""SQLite identity store for the Foroba backend (suite identity authority)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from auth.security import hash_password
from chat_crypto import decrypt, encrypt, safe_decrypt, safe_encrypt

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'free',
    audience TEXT NOT NULL DEFAULT 'base',
    audience_locked INTEGER NOT NULL DEFAULT 0,
    totp_secret TEXT,
    totp_enabled INTEGER NOT NULL DEFAULT 0,
    is_admin INTEGER NOT NULL DEFAULT 0,
    household_id TEXT,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    mfa_enrollment_pending INTEGER NOT NULL DEFAULT 0,
    session_version INTEGER NOT NULL DEFAULT 1
);

-- Per-user, per-resource-type opt-in sharing toggle. If a row exists with
-- shared=1, the user's resources of that type become visible to household
-- members (via GET /auth/visible-owners). Default (no row, or shared=0) is
-- private: only the owner can see their own data.
CREATE TABLE IF NOT EXISTS share_preferences (
    user_id INTEGER NOT NULL,
    resource_type TEXT NOT NULL,
    shared INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, resource_type)
);

CREATE TABLE IF NOT EXISTS sandbox_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    code TEXT,
    artifacts_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sandbox_user_context (
    user_id TEXT PRIMARY KEY,
    context_text TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- A (user_id, notif_key) pair the user has dismissed from the notifications
-- bell (foroba#158). notif_key is a stable, alert-instance-specific string
-- (e.g. "goal_reached:42") built by notification_service.py — dismissing
-- permanently suppresses that specific alert instance from resurfacing.
CREATE TABLE IF NOT EXISTS notification_dismissals (
    user_id INTEGER NOT NULL,
    notif_key TEXT NOT NULL,
    dismissed_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, notif_key)
);

-- Last-seen amount for a Pazuru RecurringPattern, per user. Pazuru's
-- RecurringPattern only stores current state (no history), so Foroba tracks
-- its own baseline to detect a "recurring payment increased" alert
-- (notification_service.py) across successive checks.
CREATE TABLE IF NOT EXISTS recurring_amount_baselines (
    user_id INTEGER NOT NULL,
    pattern_id INTEGER NOT NULL,
    last_amount_cents INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, pattern_id)
);

-- Named, saveable what-if scenario parameters (foroba#162, TI-D item 1). Only
-- parameters are stored — projections are always recomputed live against
-- current data. Visible to the whole household (household_id) when the
-- creator has one, otherwise private to created_by_user_id.
CREATE TABLE IF NOT EXISTS whatif_scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_by_user_id INTEGER NOT NULL,
    household_id TEXT,
    name TEXT NOT NULL,
    horizon_months INTEGER NOT NULL,
    params_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Monthly AI-generated financial summary (foroba#159, TI-D item 2). Multiple rows
-- per (user_id, year_month) are allowed on purpose (never overwritten) — capped by
-- MONTHLY_REPORT_LIMIT quota check in monthly_report_service.py, not by this table.
CREATE TABLE IF NOT EXISTS monthly_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    year_month TEXT NOT NULL,
    trigger TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    narrative_text TEXT,
    context_snapshot_json TEXT,
    error_message TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Cached EUR-based FX rates (TI-D item 3 Plan 3, foroba#164). EUR itself is never
-- stored — implicit rate 1.0, short-circuited in fx_service.py. Mirrors Pazuru's
-- fx_rates (SQLAlchemy) and Tsumi's fx_rates (DuckDB) table shape.
CREATE TABLE IF NOT EXISTS fx_rates (
    currency TEXT NOT NULL,
    rate_to_eur REAL NOT NULL,
    rate_date TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (currency, rate_date)
);

-- Personal API keys for the public read API (foroba#165, TI-D item 5, Plan A).
-- key_prefix is looked up directly (indexed, unique) so verification never scans
-- the whole table; secret_hash is argon2id (auth/security.py hash_password).
CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    key_prefix TEXT NOT NULL UNIQUE,
    secret_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    last_used_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Subscription billing (BR-12). Provider ids only: no card data, no raw webhook payloads.
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    provider TEXT NOT NULL,
    provider_subscription_id TEXT NOT NULL,
    provider_customer_id TEXT,
    status TEXT NOT NULL,
    current_period_end TEXT,
    cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
    last_event_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (provider, provider_subscription_id)
);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions (user_id);

-- Idempotency ledger: one row per processed webhook event id.
CREATE TABLE IF NOT EXISTS billing_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    received_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Public-site waitlist (Plan D, S1). Double opt-in; token stored only as SHA-256.
CREATE TABLE IF NOT EXISTS waitlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    apps TEXT NOT NULL DEFAULT '',
    lang TEXT NOT NULL DEFAULT 'en',
    consent_at TEXT NOT NULL,
    confirm_token_hash TEXT,
    confirmed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_waitlist_token ON waitlist(confirm_token_hash);

-- Registered webhook targets (foroba#165, TI-D item 5, Plan A). signing_secret is
-- stored plaintext — it is needed on every delivery to compute the outgoing HMAC,
-- unlike a login credential it is never used to authenticate an inbound request.
CREATE TABLE IF NOT EXISTS webhooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    target_url TEXT NOT NULL,
    signing_secret TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    disabled_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Dedup ledger + retry-state tracker for webhook_dispatch_job.py (foroba#165). An
-- event (webhook_id, event_key) never fires twice successfully to the same webhook.
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    webhook_id INTEGER NOT NULL,
    event_key TEXT NOT NULL,
    delivered_at TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_status TEXT,
    UNIQUE(webhook_id, event_key)
);

CREATE TABLE IF NOT EXISTS recovery_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    code_hash TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS email_otp_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    code_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS webauthn_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    credential_id TEXT NOT NULL UNIQUE,
    public_key TEXT NOT NULL,
    sign_count INTEGER NOT NULL DEFAULT 0,
    label TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS webauthn_challenges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    challenge TEXT NOT NULL,
    purpose TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Versioned ToS/Privacy Policy consent record (GDPR Art. 5 accountability,
-- foroba#219). One row per (user, document_type) acceptance event — a user who
-- re-accepts a new version gets a new row, the old one is left untouched as the
-- historical record of what they agreed to and when.
CREATE TABLE IF NOT EXISTS consents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    document_type TEXT NOT NULL,
    document_version TEXT NOT NULL,
    accepted_at TEXT NOT NULL DEFAULT (datetime('now')),
    ip_address TEXT
);

-- Admin-generated invite codes (GL-10.1, foroba#185). Redemption is only enforced at
-- registration when the `require_invite_code` runtime setting is true (settings_store.py) —
-- off by default, so self-host deployments are unaffected. uses_count is incremented
-- atomically on each successful redemption; a code is valid while not revoked, not expired,
-- and uses_count < max_uses.
CREATE TABLE IF NOT EXISTS invite_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    note TEXT,
    max_uses INTEGER NOT NULL DEFAULT 1,
    uses_count INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT,
    revoked_at TEXT,
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Opaque rotating refresh tokens for cookieless native clients (iOS/CLI).
-- The plaintext token is never stored; only a SHA-256 hex hash is persisted.
-- family_id groups a token and all its rotated successors so reuse detection can
-- revoke the whole chain in one statement (RFC 6819 §5.2.2.3).
-- IOS-0 / pfh-mobile#3.
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash   TEXT    NOT NULL UNIQUE,
    family_id    TEXT    NOT NULL,
    device_label TEXT,
    created_at   TEXT    NOT NULL,
    last_used_at TEXT,
    expires_at   TEXT    NOT NULL,
    revoked_at   TEXT
);
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user   ON refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_family ON refresh_tokens (family_id);
"""


def _split_full_name(name: str) -> tuple[str, str]:
    parts = (name or "").strip().split(" ", 1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else ""
    return first, last


# AI-4-F4: one consent row per (user, document, version). Not in SCHEMA because databases
# that already hold duplicate rows would fail the CREATE UNIQUE INDEX there; the redundant
# copies are dropped first (the earliest row keeps the true first-acceptance timestamp).
CONSENT_DEDUPE_SQL = (
    "DELETE FROM consents WHERE id NOT IN ("
    "SELECT MIN(id) FROM consents GROUP BY user_id, document_type, document_version)"
)
CONSENT_UNIQUE_INDEX_SQL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_consents_user_doc_version "
    "ON consents(user_id, document_type, document_version)"
)


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
    conn.execute(CONSENT_DEDUPE_SQL)
    conn.execute(CONSENT_UNIQUE_INDEX_SQL)
    conn.commit()
    # Idempotent migration: add is_admin column if it doesn't exist
    try:
        conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    # Idempotent migration: add household_id column if it doesn't exist
    try:
        conn.execute("ALTER TABLE users ADD COLUMN household_id TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    # Idempotent migration: add display_currency column if it doesn't exist
    try:
        conn.execute("ALTER TABLE users ADD COLUMN display_currency TEXT NOT NULL DEFAULT 'EUR'")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    # Idempotent migration: add show_debts column if it doesn't exist
    try:
        conn.execute("ALTER TABLE users ADD COLUMN show_debts INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    # Idempotent migration: add birth_year/country (optional profile fields) +
    # onboarding_completed_at (new-user guided setup tracking) if they don't exist
    try:
        conn.execute("ALTER TABLE users ADD COLUMN birth_year INTEGER")
        conn.execute("ALTER TABLE users ADD COLUMN country TEXT")
        conn.execute("ALTER TABLE users ADD COLUMN onboarding_completed_at TEXT")
        # Backfill existing users as "already onboarded" so they never see the
        # new guided setup flow — only genuinely new registrations get NULL.
        conn.execute("UPDATE users SET onboarding_completed_at = datetime('now')")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # columns already exist
    # Idempotent migration: add first_name/last_name/avatar_url (suite identity,
    # shared Topbar UserMenu) if they don't exist, backfilling from `name`.
    try:
        conn.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
        conn.execute("ALTER TABLE users ADD COLUMN last_name TEXT")
        conn.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
        conn.commit()
        rows = conn.execute("SELECT id, name FROM users").fetchall()
        for row in rows:
            first, last = _split_full_name(row["name"])
            conn.execute(
                "UPDATE users SET first_name = ?, last_name = ? WHERE id = ?",
                (first, last, row["id"]),
            )
        conn.commit()
    except sqlite3.OperationalError:
        pass  # columns already exist
    # Idempotent migration: add account_disabled column if it doesn't exist
    # (GL-10.1, foroba#190 — admin panel "disable account" action).
    try:
        conn.execute("ALTER TABLE users ADD COLUMN account_disabled INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    # Idempotent migration: add email_otp_enabled/webauthn_enabled flags (MFA hardening, foroba#199)
    try:
        conn.execute("ALTER TABLE users ADD COLUMN email_otp_enabled INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    try:
        conn.execute("ALTER TABLE users ADD COLUMN webauthn_enabled INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    # Idempotent migration: add mfa_enrollment_pending flag (GL-4.2, foroba#173 — 2FA on by
    # default for new signups). Defaults to 0 so existing users are never retroactively
    # forced into enrollment; only register() sets it to 1 for brand-new accounts.
    try:
        conn.execute(
            "ALTER TABLE users ADD COLUMN mfa_enrollment_pending INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    # CL-2.2 (foroba#239): DSAR processing-restriction/objection flags
    try:
        conn.execute(
            "ALTER TABLE users ADD COLUMN processing_restricted INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    try:
        conn.execute(
            "ALTER TABLE users ADD COLUMN marketing_objection INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    # CL-2.4 (foroba#241): security event audit log
    conn.execute(
        "CREATE TABLE IF NOT EXISTS security_events ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " user_id INTEGER,"
        " event TEXT NOT NULL,"
        " detail TEXT,"
        " ip TEXT,"
        " created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    conn.commit()
    # CL-2.2 (foroba#239): DSAR request tracking log
    conn.execute(
        "CREATE TABLE IF NOT EXISTS dsar_requests ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " user_id INTEGER NOT NULL REFERENCES users(id),"
        " kind TEXT NOT NULL,"
        " status TEXT NOT NULL DEFAULT 'open',"
        " created_at TEXT NOT NULL DEFAULT (datetime('now')),"
        " resolved_at TEXT,"
        " note TEXT)"
    )
    conn.commit()
    # A2 (foroba#178): email_verified flag — DEFAULT 1 so existing users are not affected.
    # New users get 0 when SMTP is enabled; set to 1 via POST /auth/verify-email.
    try:
        conn.execute(
            "ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1"
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    # A6 (foroba#182): pending_email — stores new address during change flow,
    # cleared once the OTP is verified and the address is applied.
    try:
        conn.execute("ALTER TABLE users ADD COLUMN pending_email TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    # A4 (foroba#180): household invites table.
    # token is a 12-char alphanumeric code that expires in 48h and is single-use.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS household_invites ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " inviter_id INTEGER NOT NULL REFERENCES users(id),"
        " household_id TEXT NOT NULL,"
        " invited_email TEXT NOT NULL,"
        " token_hash TEXT NOT NULL UNIQUE,"
        " expires_at TEXT NOT NULL,"
        " accepted_at TEXT,"
        " created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    conn.commit()
    # IOS-4 (#37): device push-token table for APNs/FCM groundwork.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS device_push_tokens ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,"
        " token TEXT NOT NULL,"
        " platform TEXT NOT NULL,"
        " registered_at TEXT NOT NULL,"
        " UNIQUE(user_id, token))"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_device_push_tokens_user_id"
        " ON device_push_tokens(user_id)"
    )
    conn.commit()
    # FOR-D06: totp_secret_pending stages a newly generated TOTP secret separately from the
    # live totp_secret column, so /auth/2fa/enroll can no longer silently disable an already
    # -working MFA method before /verify confirms the new one (see auth/repository.py's
    # set_totp_secret()/enable_totp()).
    try:
        conn.execute("ALTER TABLE users ADD COLUMN totp_secret_pending TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists


# (email, name, plaintext password, tier, audience, is_admin)
MOCK_USERS = [
    ("demo@foroba.app", "Demo Base", "Demo!2026", "free", "base", 0),
    ("pro@foroba.app", "Pro Expert", "Pro!2026", "premium", "expert", 0),
    ("test@foroba.app", "Test User", "Test!2026", "free", "base", 0),
    ("admin@foroba.app", "Foroba Admin", "Admin1234!", "free", "base", 1),
]

# Emails that are local-dev-only seed accounts and must not exist in hosted (prod) mode.
# admin@foroba.app is intentionally excluded: it is a legitimate ops account whose
# password was already rotated on prod. Purging it would lock out the admin panel.
_SEED_ONLY_EMAILS = ("demo@foroba.app", "pro@foroba.app", "test@foroba.app")


def purge_mock_users(conn: sqlite3.Connection) -> list[str]:
    """Delete local-dev-only seed accounts when running in hosted mode (foroba#254).

    Called from _startup() whenever deployment_mode == "hosted", regardless of
    seed_mock_users — this cleans up any rows seeded before the hosted guard was
    tightened, ensuring well-known-password accounts never survive to production.
    Returns the list of emails that were actually deleted.
    """
    deleted: list[str] = []
    for email in _SEED_ONLY_EMAILS:
        cur = conn.execute("DELETE FROM users WHERE email = ?", (email,))
        if cur.rowcount:
            deleted.append(email)
    conn.commit()
    return deleted


def seed_mock_users(conn: sqlite3.Connection) -> list[str]:
    """Insert mock users that do not already exist. Returns created emails."""
    created: list[str] = []
    for email, name, pw, tier, audience, is_admin in MOCK_USERS:
        exists = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO users (email, name, password_hash, tier, audience, is_admin) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (email, name, hash_password(pw), tier, audience, is_admin),
        )
        created.append(email)
    conn.commit()
    return created


# Fixed demo household linking demo@foroba.app + pro@foroba.app for local dev/testing
# of the FB-5 household-sharing feature. Sharing itself stays OFF (private) by default
# — a user must explicitly opt in via PUT /auth/household/share. test@foroba.app is
# intentionally left with no household_id, to exercise the isolated/private-only path.
_DEMO_HOUSEHOLD_ID = "demo-household-0001"
_DEMO_HOUSEHOLD_EMAILS = ("demo@foroba.app", "pro@foroba.app")


def seed_demo_household(conn: sqlite3.Connection) -> None:
    for email in _DEMO_HOUSEHOLD_EMAILS:
        row = conn.execute(
            "SELECT id, household_id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if row is None or row["household_id"]:
            continue
        conn.execute(
            "UPDATE users SET household_id = ? WHERE id = ?", (_DEMO_HOUSEHOLD_ID, row["id"])
        )
    conn.commit()


def save_sandbox_turn(
    conn: sqlite3.Connection,
    user_id: str,
    session_id: str,
    question: str,
    answer: str,
    code: str | None = None,
    artifacts_json: str | None = None,
) -> None:
    """Persist a user question + assistant answer as two conversation rows.

    `content`/`code` are Fernet-encrypted at rest (GL-11.3) — see chat_crypto.py.
    """
    conn.execute(
        "INSERT INTO sandbox_conversations (user_id, session_id, role, content) "
        "VALUES (?, ?, 'user', ?)",
        (user_id, session_id, encrypt(question)),
    )
    encrypted_code = encrypt(code) if code is not None else None
    conn.execute(
        "INSERT INTO sandbox_conversations "
        "(user_id, session_id, role, content, code, artifacts_json) "
        "VALUES (?, ?, 'assistant', ?, ?, ?)",
        (user_id, session_id, encrypt(answer), encrypted_code, artifacts_json),
    )
    conn.commit()


def get_sandbox_history(
    conn: sqlite3.Connection, user_id: str, session_id: str, limit: int = 20
) -> list[dict]:
    """Return the most recent `limit` conversation rows, in chronological order.

    `content`/`code` are decrypted transparently here (GL-11.3) — see chat_crypto.py.
    """
    rows = conn.execute(
        "SELECT role, content, code FROM sandbox_conversations "
        "WHERE user_id = ? AND session_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
        (user_id, session_id, limit),
    ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["content"] = decrypt(d["content"])
        if d["code"] is not None:
            d["code"] = decrypt(d["code"])
        result.append(d)
    result.reverse()
    return result


def get_sandbox_user_context(conn: sqlite3.Connection, user_id: str) -> str:
    row = conn.execute(
        "SELECT context_text FROM sandbox_user_context WHERE user_id = ?", (user_id,)
    ).fetchone()
    return safe_decrypt(row["context_text"]) or "" if row else ""


def update_sandbox_user_context(conn: sqlite3.Connection, user_id: str, context_text: str) -> None:
    conn.execute(
        "INSERT INTO sandbox_user_context (user_id, context_text, updated_at) "
        "VALUES (?, ?, datetime('now')) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "context_text = excluded.context_text, updated_at = excluded.updated_at",
        (user_id, safe_encrypt(context_text)),
    )
    conn.commit()


def get_dismissed_notification_keys(conn: sqlite3.Connection, user_id: int) -> set[str]:
    rows = conn.execute(
        "SELECT notif_key FROM notification_dismissals WHERE user_id = ?", (user_id,)
    ).fetchall()
    return {r["notif_key"] for r in rows}


def dismiss_notification(conn: sqlite3.Connection, user_id: int, notif_key: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO notification_dismissals (user_id, notif_key) VALUES (?, ?)",
        (user_id, notif_key),
    )
    conn.commit()


def get_recurring_baseline(conn: sqlite3.Connection, user_id: int, pattern_id: int) -> int | None:
    row = conn.execute(
        "SELECT last_amount_cents FROM recurring_amount_baselines "
        "WHERE user_id = ? AND pattern_id = ?",
        (user_id, pattern_id),
    ).fetchone()
    return row["last_amount_cents"] if row else None


def set_recurring_baseline(
    conn: sqlite3.Connection, user_id: int, pattern_id: int, amount_cents: int
) -> None:
    conn.execute(
        "INSERT INTO recurring_amount_baselines "
        "(user_id, pattern_id, last_amount_cents, updated_at) "
        "VALUES (?, ?, ?, datetime('now')) "
        "ON CONFLICT(user_id, pattern_id) DO UPDATE SET "
        "last_amount_cents = excluded.last_amount_cents, updated_at = excluded.updated_at",
        (user_id, pattern_id, amount_cents),
    )
    conn.commit()


def _whatif_visibility_clause() -> str:
    return "(household_id = ? OR (household_id IS NULL AND created_by_user_id = ?))"


def _decrypt_whatif_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["params_json"] = safe_decrypt(d.get("params_json"))
    return d


def create_whatif_scenario(
    conn: sqlite3.Connection,
    *,
    created_by_user_id: int,
    household_id: str | None,
    name: str,
    horizon_months: int,
    params_json: str,
) -> dict:
    cur = conn.execute(
        "INSERT INTO whatif_scenarios "
        "(created_by_user_id, household_id, name, horizon_months, params_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (created_by_user_id, household_id, name, horizon_months, safe_encrypt(params_json)),
    )
    conn.commit()
    row = get_whatif_scenario(
        conn, cur.lastrowid, user_id=created_by_user_id, household_id=household_id
    )
    assert row is not None
    return row


def list_whatif_scenarios(
    conn: sqlite3.Connection, *, user_id: int, household_id: str | None
) -> list[dict]:
    rows = conn.execute(
        f"SELECT * FROM whatif_scenarios WHERE {_whatif_visibility_clause()} "
        "ORDER BY created_at DESC, id DESC",
        (household_id, user_id),
    ).fetchall()
    return [_decrypt_whatif_row(r) for r in rows]


def get_whatif_scenario(
    conn: sqlite3.Connection, scenario_id: int, *, user_id: int, household_id: str | None
) -> dict | None:
    row = conn.execute(
        f"SELECT * FROM whatif_scenarios WHERE id = ? AND {_whatif_visibility_clause()}",
        (scenario_id, household_id, user_id),
    ).fetchone()
    return _decrypt_whatif_row(row) if row is not None else None


def update_whatif_scenario(
    conn: sqlite3.Connection,
    scenario_id: int,
    *,
    user_id: int,
    household_id: str | None,
    name: str,
    horizon_months: int,
    params_json: str,
) -> dict | None:
    if get_whatif_scenario(conn, scenario_id, user_id=user_id, household_id=household_id) is None:
        return None
    conn.execute(
        "UPDATE whatif_scenarios SET name = ?, horizon_months = ?, params_json = ?, "
        "updated_at = datetime('now') WHERE id = ?",
        (name, horizon_months, safe_encrypt(params_json), scenario_id),
    )
    conn.commit()
    return get_whatif_scenario(conn, scenario_id, user_id=user_id, household_id=household_id)


def delete_whatif_scenario(
    conn: sqlite3.Connection, scenario_id: int, *, user_id: int, household_id: str | None = None
) -> bool:
    if get_whatif_scenario(conn, scenario_id, user_id=user_id, household_id=household_id) is None:
        return False
    conn.execute("DELETE FROM whatif_scenarios WHERE id = ?", (scenario_id,))
    conn.commit()
    return True


def run_migrations(db_path: str) -> None:
    """Apply all pending Alembic migrations to the SQLite file at db_path."""
    from alembic.config import Config

    from alembic import command

    backend_dir = Path(__file__).resolve().parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    # ConfigParser (which Config.set_main_option delegates to) interpolates `%`
    # as an escape char — a SQLCipher URL's percent-encoded password (e.g. the
    # `=` padding in a base64 key becomes `%3D`) trips "invalid interpolation
    # syntax" unless every literal `%` is doubled first (alembic's own
    # documented workaround for passwords containing `%`).
    cfg.set_main_option("sqlalchemy.url", _alembic_url(db_path).replace("%", "%%"))
    command.upgrade(cfg, "head")


def _alembic_url(db_path: str) -> str:
    """Build the Alembic `sqlalchemy.url` for db_path.

    GL-11.2: when db_encryption_key is set, db_path is a SQLCipher-encrypted
    file and Alembic must connect via the sqlite+pysqlcipher dialect with the
    passphrase instead of plain sqlite (which can't read the ciphertext header).
    """
    from config import settings

    if settings.db_encryption_key:
        from sqlalchemy.engine import URL

        url = URL.create(
            drivername="sqlite+pysqlcipher",
            username="",  # forces URL to render ":password@" — omitted entirely if None
            password=settings.db_encryption_key,
            database=db_path,
        )
        return url.render_as_string(hide_password=False)
    return f"sqlite:///{db_path}"


def connect(db_path: str) -> sqlite3.Connection:
    """Open a connection to db_path, applying migrations first.

    GL-11.2: when settings.db_encryption_key is set, this uses sqlcipher3's
    DBAPI (sqlite3-compatible) instead of stdlib sqlite3, and issues
    `PRAGMA key` immediately after connecting (before any other statement)
    to decrypt the SQLCipher-encrypted file. Separate trust boundary from
    the per-column Fernet field_encryption_key.

    `:memory:` is always handled via stdlib sqlite3, regardless of
    db_encryption_key: encryption-at-rest is meaningless for a transient,
    process-local in-memory DB (nothing is ever persisted to disk), and
    sqlcipher3's `:memory:` connections were observed to share state across
    independent `connect(":memory:")` calls within the same process
    (test suite hit "duplicate column" errors from init_schema() running
    twice against what should have been two isolated in-memory DBs).
    """
    from config import settings

    if db_path == ":memory:":
        conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        init_schema(conn)
        return conn

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    if settings.db_encryption_key:
        import sqlcipher3.dbapi2 as sqlcipher

        escaped_key = settings.db_encryption_key.replace("'", "''")

        run_migrations(db_path)
        conn = sqlcipher.connect(db_path, check_same_thread=False, timeout=10)
        conn.execute(f"PRAGMA key = '{escaped_key}'")
        conn.row_factory = sqlcipher.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    run_migrations(db_path)
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    # This connection is shared (singleton) across all threadpool workers
    # handling concurrent requests (see auth/conn.py). The default SQLite
    # rollback-journal mode locks the whole DB file per writer, and Python's
    # sqlite3 default busy timeout (5s) was left implicit. Under concurrent
    # writes (e.g. many logins updating failed_login_attempts) this produced
    # "database is locked" 500s. WAL lets readers run concurrently with the
    # single writer, and an explicit busy_timeout makes writers queue instead
    # of failing immediately when they do contend.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def create_monthly_report(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    year_month: str,
    trigger: str,
) -> sqlite3.Row:
    cur = conn.execute(
        "INSERT INTO monthly_reports (user_id, year_month, trigger, status) "
        "VALUES (?, ?, ?, 'generating')",
        (user_id, year_month, trigger),
    )
    conn.commit()
    row = get_monthly_report(conn, cur.lastrowid, user_id=user_id)
    assert row is not None
    return row


def _decrypt_monthly_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["narrative_text"] = safe_decrypt(d.get("narrative_text"))
    d["context_snapshot_json"] = safe_decrypt(d.get("context_snapshot_json"))
    return d


def get_monthly_report(
    conn: sqlite3.Connection, report_id: int, *, user_id: int
) -> dict | None:
    row = conn.execute(
        "SELECT * FROM monthly_reports WHERE id = ? AND user_id = ?",
        (report_id, user_id),
    ).fetchone()
    return _decrypt_monthly_row(row) if row is not None else None


def list_monthly_reports(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    year_month: str | None = None,
) -> list[dict]:
    if year_month:
        rows = conn.execute(
            "SELECT * FROM monthly_reports WHERE user_id = ? AND year_month = ? "
            "ORDER BY created_at DESC, id DESC",
            (user_id, year_month),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM monthly_reports WHERE user_id = ? ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()
    return [_decrypt_monthly_row(r) for r in rows]


def count_monthly_reports_this_month(
    conn: sqlite3.Connection, *, user_id: int, year_month: str
) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM monthly_reports WHERE user_id = ? AND year_month = ?",
        (user_id, year_month),
    ).fetchone()
    return row["n"]


def update_monthly_report_result(
    conn: sqlite3.Connection,
    report_id: int,
    *,
    status: str,
    narrative_text: str | None,
    context_snapshot_json: str | None,
    error_message: str | None,
    attempt_count: int,
) -> dict | None:
    conn.execute(
        "UPDATE monthly_reports SET status = ?, narrative_text = ?, context_snapshot_json = ?, "
        "error_message = ?, attempt_count = ?, updated_at = datetime('now') WHERE id = ?",
        (
            status,
            safe_encrypt(narrative_text),
            safe_encrypt(context_snapshot_json),
            error_message,
            attempt_count,
            report_id,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM monthly_reports WHERE id = ?", (report_id,)).fetchone()
    return _decrypt_monthly_row(row) if row is not None else None


def create_api_key(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    label: str,
    key_prefix: str,
    secret_hash: str,
) -> sqlite3.Row:
    cur = conn.execute(
        "INSERT INTO api_keys (user_id, label, key_prefix, secret_hash) VALUES (?, ?, ?, ?)",
        (user_id, label, key_prefix, secret_hash),
    )
    conn.commit()
    row = get_api_key_by_id(conn, cur.lastrowid, user_id=user_id)
    assert row is not None
    return row


def get_api_key_by_id(conn: sqlite3.Connection, key_id: int, *, user_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM api_keys WHERE id = ? AND user_id = ?",
        (key_id, user_id),
    ).fetchone()


def get_api_key_by_prefix(conn: sqlite3.Connection, key_prefix: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM api_keys WHERE key_prefix = ?", (key_prefix,)).fetchone()


def list_api_keys(conn: sqlite3.Connection, *, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM api_keys WHERE user_id = ? ORDER BY created_at DESC, id DESC",
        (user_id,),
    ).fetchall()


def revoke_api_key(conn: sqlite3.Connection, key_id: int, *, user_id: int) -> bool:
    cur = conn.execute(
        "UPDATE api_keys SET is_active = 0 WHERE id = ? AND user_id = ?",
        (key_id, user_id),
    )
    conn.commit()
    return cur.rowcount > 0


def touch_api_key_last_used(conn: sqlite3.Connection, key_id: int) -> None:
    conn.execute("UPDATE api_keys SET last_used_at = datetime('now') WHERE id = ?", (key_id,))
    conn.commit()


def create_webhook(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    target_url: str,
    signing_secret: str,
) -> sqlite3.Row:
    cur = conn.execute(
        "INSERT INTO webhooks (user_id, target_url, signing_secret) VALUES (?, ?, ?)",
        (user_id, target_url, signing_secret),
    )
    conn.commit()
    row = get_webhook(conn, cur.lastrowid, user_id=user_id)
    assert row is not None
    return row


def get_webhook(conn: sqlite3.Connection, webhook_id: int, *, user_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM webhooks WHERE id = ? AND user_id = ?",
        (webhook_id, user_id),
    ).fetchone()


def list_webhooks(conn: sqlite3.Connection, *, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM webhooks WHERE user_id = ? ORDER BY created_at DESC, id DESC",
        (user_id,),
    ).fetchall()


def list_active_webhooks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """All active webhooks across all users — used by the dispatch job."""
    return conn.execute("SELECT * FROM webhooks WHERE is_active = 1").fetchall()


def delete_webhook(conn: sqlite3.Connection, webhook_id: int, *, user_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM webhooks WHERE id = ? AND user_id = ?",
        (webhook_id, user_id),
    )
    conn.commit()
    return cur.rowcount > 0


def reactivate_webhook(
    conn: sqlite3.Connection, webhook_id: int, *, user_id: int
) -> sqlite3.Row | None:
    conn.execute(
        "UPDATE webhooks SET is_active = 1, consecutive_failures = 0, disabled_at = NULL "
        "WHERE id = ? AND user_id = ?",
        (webhook_id, user_id),
    )
    conn.commit()
    return get_webhook(conn, webhook_id, user_id=user_id)


def register_webhook_failure(conn: sqlite3.Connection, webhook_id: int) -> sqlite3.Row:
    """Increment consecutive_failures; auto-disable at the 10-failure threshold."""
    conn.execute(
        "UPDATE webhooks SET consecutive_failures = consecutive_failures + 1 WHERE id = ?",
        (webhook_id,),
    )
    row = conn.execute("SELECT * FROM webhooks WHERE id = ?", (webhook_id,)).fetchone()
    if row["consecutive_failures"] >= 10:
        conn.execute(
            "UPDATE webhooks SET is_active = 0, disabled_at = datetime('now') WHERE id = ?",
            (webhook_id,),
        )
    conn.commit()
    return conn.execute("SELECT * FROM webhooks WHERE id = ?", (webhook_id,)).fetchone()


def reset_webhook_failures(conn: sqlite3.Connection, webhook_id: int) -> None:
    conn.execute("UPDATE webhooks SET consecutive_failures = 0 WHERE id = ?", (webhook_id,))
    conn.commit()


def get_webhook_delivery(
    conn: sqlite3.Connection, webhook_id: int, event_key: str
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM webhook_deliveries WHERE webhook_id = ? AND event_key = ?",
        (webhook_id, event_key),
    ).fetchone()


def upsert_webhook_delivery_success(
    conn: sqlite3.Connection,
    webhook_id: int,
    event_key: str,
    attempt_count: int,
) -> None:
    conn.execute(
        "INSERT INTO webhook_deliveries "
        "(webhook_id, event_key, delivered_at, attempt_count, last_status) "
        "VALUES (?, ?, datetime('now'), ?, 'success') "
        "ON CONFLICT(webhook_id, event_key) DO UPDATE SET "
        "delivered_at = excluded.delivered_at, attempt_count = excluded.attempt_count, "
        "last_status = excluded.last_status",
        (webhook_id, event_key, attempt_count),
    )
    conn.commit()


def upsert_webhook_delivery_attempt(
    conn: sqlite3.Connection,
    webhook_id: int,
    event_key: str,
    *,
    attempt_count: int,
    status: str,
) -> None:
    """status is 'pending' (will retry next tick) or 'failed' (exhausted retries)."""
    conn.execute(
        "INSERT INTO webhook_deliveries (webhook_id, event_key, attempt_count, last_status) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(webhook_id, event_key) DO UPDATE SET "
        "attempt_count = excluded.attempt_count, last_status = excluded.last_status",
        (webhook_id, event_key, attempt_count, status),
    )
    conn.commit()
