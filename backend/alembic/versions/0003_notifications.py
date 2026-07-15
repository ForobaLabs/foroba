"""notifications — dismissals + recurring-amount baselines

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-16

Adds notification_dismissals + recurring_amount_baselines (see db.py::SCHEMA)
for the notifications/alerts feature (foroba#158, TI-C).
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_dismissals (
            user_id INTEGER NOT NULL,
            notif_key TEXT NOT NULL,
            dismissed_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, notif_key)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS recurring_amount_baselines (
            user_id INTEGER NOT NULL,
            pattern_id INTEGER NOT NULL,
            last_amount_cents INTEGER NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, pattern_id)
        )
        """
    )


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
