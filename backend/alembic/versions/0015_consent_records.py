"""consents table — versioned ToS/Privacy Policy acceptance record (foroba#219)

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-06 00:00:00.000000

"""

from __future__ import annotations

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS consents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            document_type TEXT NOT NULL,
            document_version TEXT NOT NULL,
            accepted_at TEXT NOT NULL DEFAULT (datetime('now')),
            ip_address TEXT
        )
        """
    )


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
