"""waitlist table for the public site (Plan D, S1).

Only a new table (the users table is untouched). Mirrors db.SCHEMA; IF NOT EXISTS makes
this a no-op on databases created fresh from SCHEMA.

Revision ID: 0026_waitlist
Revises: 0025_billing
"""

from __future__ import annotations

from alembic import op

revision = "0026_waitlist"
down_revision = "0025_billing"
branch_labels = None
depends_on = None

_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS waitlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        apps TEXT NOT NULL DEFAULT '',
        lang TEXT NOT NULL DEFAULT 'en',
        consent_at TEXT NOT NULL,
        confirm_token_hash TEXT,
        confirmed_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_waitlist_token ON waitlist(confirm_token_hash)",
]


def upgrade() -> None:
    for stmt in _STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
