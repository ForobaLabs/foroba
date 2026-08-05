"""users.mfa_enrollment_pending column (GL-4.2, foroba#173 — 2FA on by default for new signups)

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-06 00:00:00.000000

"""

from __future__ import annotations

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN mfa_enrollment_pending INTEGER NOT NULL DEFAULT 0")


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
