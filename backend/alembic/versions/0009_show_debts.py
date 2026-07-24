"""users.show_debts column (TI-D item 6, Pazuru debts module net-worth toggle)"""
from __future__ import annotations

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN show_debts INTEGER NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
