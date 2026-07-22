"""users.display_currency column (TI-D item 3 Plan 3, foroba#164)"""
from __future__ import annotations

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN display_currency TEXT NOT NULL DEFAULT 'EUR'"
    )


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
