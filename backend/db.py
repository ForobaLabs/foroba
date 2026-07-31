"""SQLite identity store for the Foroba backend (suite identity authority)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from auth.security import hash_password
from chat_crypto import decrypt, encrypt

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
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
"""


def _split_full_name(name: str) -> tuple[str, str]:
    parts = (name or "").strip().split(" ", 1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else ""
    return first, last


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
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


# (email, name, plaintext password, tier, audience, is_admin)
MOCK_USERS = [
    ("demo@foroba.app", "Demo Base", "Demo!2026", "free", "base", 0),
    ("pro@foroba.app", "Pro Expert", "Pro!2026", "premium", "expert", 0),
    ("test@foroba.app", "Test User", "Test!2026", "free", "base", 0),
    ("admin@foroba.app", "Foroba Admin", "Admin1234!", "free", "base", 1),
]


def seed_mock_users(conn: sqlite3.Connection) -> list[str]:
    """Insert mock users that do not already exist. Returns created emails."""
    created: list[str] = []
    for email, name, pw, tier, audience, is_admin in MOCK_USERS:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE email = ?", (email,)
        ).fetchone()
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
    return row["context_text"] if row else ""


def update_sandbox_user_context(conn: sqlite3.Connection, user_id: str, context_text: str) -> None:
    conn.execute(
        "INSERT INTO sandbox_user_context (user_id, context_text, updated_at) "
        "VALUES (?, ?, datetime('now')) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "context_text = excluded.context_text, updated_at = excluded.updated_at",
        (user_id, context_text),
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


def create_whatif_scenario(
    conn: sqlite3.Connection, *, created_by_user_id: int, household_id: str | None,
    name: str, horizon_months: int, params_json: str,
) -> sqlite3.Row:
    cur = conn.execute(
        "INSERT INTO whatif_scenarios "
        "(created_by_user_id, household_id, name, horizon_months, params_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (created_by_user_id, household_id, name, horizon_months, params_json),
    )
    conn.commit()
    row = get_whatif_scenario(
        conn, cur.lastrowid, user_id=created_by_user_id, household_id=household_id
    )
    assert row is not None
    return row


def list_whatif_scenarios(
    conn: sqlite3.Connection, *, user_id: int, household_id: str | None
) -> list[sqlite3.Row]:
    return conn.execute(
        f"SELECT * FROM whatif_scenarios WHERE {_whatif_visibility_clause()} "
        "ORDER BY created_at DESC, id DESC",
        (household_id, user_id),
    ).fetchall()


def get_whatif_scenario(
    conn: sqlite3.Connection, scenario_id: int, *, user_id: int, household_id: str | None
) -> sqlite3.Row | None:
    return conn.execute(
        f"SELECT * FROM whatif_scenarios WHERE id = ? AND {_whatif_visibility_clause()}",
        (scenario_id, household_id, user_id),
    ).fetchone()


def update_whatif_scenario(
    conn: sqlite3.Connection, scenario_id: int, *, user_id: int, household_id: str | None,
    name: str, horizon_months: int, params_json: str,
) -> sqlite3.Row | None:
    if get_whatif_scenario(conn, scenario_id, user_id=user_id, household_id=household_id) is None:
        return None
    conn.execute(
        "UPDATE whatif_scenarios SET name = ?, horizon_months = ?, params_json = ?, "
        "updated_at = datetime('now') WHERE id = ?",
        (name, horizon_months, params_json, scenario_id),
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
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    if db_path == ":memory:":
        conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        init_schema(conn)
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
    conn: sqlite3.Connection, *, user_id: int, year_month: str, trigger: str,
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


def get_monthly_report(
    conn: sqlite3.Connection, report_id: int, *, user_id: int
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM monthly_reports WHERE id = ? AND user_id = ?", (report_id, user_id),
    ).fetchone()


def list_monthly_reports(
    conn: sqlite3.Connection, *, user_id: int, year_month: str | None = None,
) -> list[sqlite3.Row]:
    if year_month:
        return conn.execute(
            "SELECT * FROM monthly_reports WHERE user_id = ? AND year_month = ? "
            "ORDER BY created_at DESC, id DESC",
            (user_id, year_month),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM monthly_reports WHERE user_id = ? ORDER BY created_at DESC, id DESC",
        (user_id,),
    ).fetchall()


def count_monthly_reports_this_month(
    conn: sqlite3.Connection, *, user_id: int, year_month: str
) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM monthly_reports WHERE user_id = ? AND year_month = ?",
        (user_id, year_month),
    ).fetchone()
    return row["n"]


def update_monthly_report_result(
    conn: sqlite3.Connection, report_id: int, *, status: str,
    narrative_text: str | None, context_snapshot_json: str | None,
    error_message: str | None, attempt_count: int,
) -> sqlite3.Row | None:
    conn.execute(
        "UPDATE monthly_reports SET status = ?, narrative_text = ?, context_snapshot_json = ?, "
        "error_message = ?, attempt_count = ?, updated_at = datetime('now') WHERE id = ?",
        (status, narrative_text, context_snapshot_json, error_message, attempt_count, report_id),
    )
    conn.commit()
    return conn.execute("SELECT * FROM monthly_reports WHERE id = ?", (report_id,)).fetchone()


def create_api_key(
    conn: sqlite3.Connection, *, user_id: int, label: str, key_prefix: str, secret_hash: str,
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
        "SELECT * FROM api_keys WHERE id = ? AND user_id = ?", (key_id, user_id),
    ).fetchone()


def get_api_key_by_prefix(conn: sqlite3.Connection, key_prefix: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM api_keys WHERE key_prefix = ?", (key_prefix,)).fetchone()


def list_api_keys(conn: sqlite3.Connection, *, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM api_keys WHERE user_id = ? ORDER BY created_at DESC, id DESC", (user_id,),
    ).fetchall()


def revoke_api_key(conn: sqlite3.Connection, key_id: int, *, user_id: int) -> bool:
    cur = conn.execute(
        "UPDATE api_keys SET is_active = 0 WHERE id = ? AND user_id = ?", (key_id, user_id),
    )
    conn.commit()
    return cur.rowcount > 0


def touch_api_key_last_used(conn: sqlite3.Connection, key_id: int) -> None:
    conn.execute("UPDATE api_keys SET last_used_at = datetime('now') WHERE id = ?", (key_id,))
    conn.commit()


def create_webhook(
    conn: sqlite3.Connection, *, user_id: int, target_url: str, signing_secret: str,
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
        "SELECT * FROM webhooks WHERE id = ? AND user_id = ?", (webhook_id, user_id),
    ).fetchone()


def list_webhooks(conn: sqlite3.Connection, *, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM webhooks WHERE user_id = ? ORDER BY created_at DESC, id DESC", (user_id,),
    ).fetchall()


def list_active_webhooks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """All active webhooks across all users — used by the dispatch job."""
    return conn.execute("SELECT * FROM webhooks WHERE is_active = 1").fetchall()


def delete_webhook(conn: sqlite3.Connection, webhook_id: int, *, user_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM webhooks WHERE id = ? AND user_id = ?", (webhook_id, user_id),
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
    conn: sqlite3.Connection, webhook_id: int, event_key: str, attempt_count: int,
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
    conn: sqlite3.Connection, webhook_id: int, event_key: str, *, attempt_count: int, status: str,
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
