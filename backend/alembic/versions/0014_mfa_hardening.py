"""recovery_codes, email_otp_codes, webauthn_credentials/_challenges tables + users MFA flags
(MFA hardening, foroba#199)

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-02 00:00:00.000000

"""

from __future__ import annotations

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS recovery_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            code_hash TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS email_otp_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            code_hash TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS webauthn_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            credential_id TEXT NOT NULL UNIQUE,
            public_key TEXT NOT NULL,
            sign_count INTEGER NOT NULL DEFAULT 0,
            label TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS webauthn_challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            challenge TEXT NOT NULL,
            purpose TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    op.execute("ALTER TABLE users ADD COLUMN email_otp_enabled INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE users ADD COLUMN webauthn_enabled INTEGER NOT NULL DEFAULT 0")


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
