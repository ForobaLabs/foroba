"""baseline — matches db.py::SCHEMA + is_admin/household_id columns

Revision ID: 0001
Revises:
Create Date: 2026-07-12

"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
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
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS share_preferences (
            user_id INTEGER NOT NULL,
            resource_type TEXT NOT NULL,
            shared INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, resource_type)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sandbox_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            code TEXT,
            artifacts_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sandbox_user_context (
            user_id TEXT PRIMARY KEY,
            context_text TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
