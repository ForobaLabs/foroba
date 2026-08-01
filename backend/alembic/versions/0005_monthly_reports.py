"""monthly_reports — AI monthly report via Jeli (foroba#159, TI-D item 2)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-21
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
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
        )
        """
    )


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
