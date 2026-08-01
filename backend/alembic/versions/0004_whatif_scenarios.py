"""whatif_scenarios — household what-if simulator (foroba#162, TI-D item 1)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-16

Adds whatif_scenarios (see db.py::SCHEMA) for the household net-worth
what-if simulator.
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS whatif_scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_by_user_id INTEGER NOT NULL,
            household_id TEXT,
            name TEXT NOT NULL,
            horizon_months INTEGER NOT NULL,
            params_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
