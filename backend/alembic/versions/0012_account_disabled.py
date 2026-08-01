"""users.account_disabled column (GL-10.1, foroba#190 — admin panel disable-account action)"""

from __future__ import annotations

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN account_disabled INTEGER NOT NULL DEFAULT 0")


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
