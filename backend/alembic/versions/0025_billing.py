"""subscriptions + billing_events tables (BR-12).

Only new tables (the users table is untouched). Mirrors db.SCHEMA; IF NOT EXISTS makes
this a no-op on databases created fresh from SCHEMA.

Revision ID: 0025_billing
Revises: 0024_session_version
"""

from __future__ import annotations

from alembic import op

revision = "0025_billing"
down_revision = "0024_session_version"
branch_labels = None
depends_on = None

_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS subscriptions (
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
    )""",
    "CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions (user_id)",
    """CREATE TABLE IF NOT EXISTS billing_events (
        event_id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        received_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
]


def upgrade() -> None:
    for stmt in _STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
