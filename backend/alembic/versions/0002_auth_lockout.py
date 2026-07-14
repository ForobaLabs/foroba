"""auth lockout — add failed_login_attempts + locked_until to users

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-15

foroba#155 / TI-B item 6: brute-force lockout for /auth/login + /auth/login/2fa.
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0"
    )
    op.execute("ALTER TABLE users ADD COLUMN locked_until TEXT")


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
