"""users.email_verified + users.pending_email columns, household_invites table.

FOR-D01: these three schema objects (foroba#178, foroba#182, foroba#180) were
added to init_schema()'s manual ALTER/CREATE block but never given a matching
Alembic migration. db.connect() only calls init_schema() for `:memory:`
connections (test suite); every real persistent SQLCipher-encrypted DB relies
solely on run_migrations() (Alembic), so these objects were silently missing
from any real install. Discovered 2026-09-13 during the deeper-audit's account
provisioning step: `POST /auth/register` raised
`OperationalError: table users has no column named email_verified` against
the live local dev DB, blocking all new user registration.

Revision ID: 0022_email_verified_household_invites
Revises: 0021_device_push_tokens
"""

from __future__ import annotations

from alembic import op

revision = "0022_email_verified_household_invites"
down_revision = "0021_device_push_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE users ADD COLUMN pending_email TEXT")
    op.execute(
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


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
