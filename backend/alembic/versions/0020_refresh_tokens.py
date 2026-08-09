"""Opaque rotating refresh tokens for cookieless native clients (IOS-0 / pfh-mobile#3)

Revision ID: 0020_refresh_tokens
Revises: 0019_security_log
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0020_refresh_tokens"
down_revision = "0019_security_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text, nullable=False, unique=True),
        sa.Column("family_id", sa.Text, nullable=False),
        sa.Column("device_label", sa.Text),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("last_used_at", sa.Text),
        sa.Column("expires_at", sa.Text, nullable=False),
        sa.Column("revoked_at", sa.Text),
    )
    op.create_index("ix_refresh_tokens_user", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_family", "refresh_tokens", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_family", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
