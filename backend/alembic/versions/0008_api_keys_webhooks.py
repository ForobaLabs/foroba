"""api_keys, webhooks, webhook_deliveries — public API + webhooks Plan A (foroba#165,
TI-D item 5)

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-22

Adds api_keys, webhooks, webhook_deliveries (see db.py::SCHEMA) for personal API-key
issuance and webhook event delivery — self-service automation surface for a user's own
scripts/n8n/Zapier/Home Assistant.
"""
from __future__ import annotations

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            label TEXT NOT NULL,
            key_prefix TEXT NOT NULL UNIQUE,
            secret_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            last_used_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            target_url TEXT NOT NULL,
            signing_secret TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            disabled_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS webhook_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            webhook_id INTEGER NOT NULL,
            event_key TEXT NOT NULL,
            delivered_at TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_status TEXT,
            UNIQUE(webhook_id, event_key)
        )
        """
    )


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
