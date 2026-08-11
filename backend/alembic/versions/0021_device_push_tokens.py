"""Device push-token table for APNs/FCM groundwork (IOS-4 / pfh-mobile#37)

Revision ID: 0021_device_push_tokens
Revises: 0020_refresh_tokens
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0021_device_push_tokens"
down_revision = "0020_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_push_tokens",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token", sa.Text, nullable=False),
        sa.Column("platform", sa.Text, nullable=False),  # 'ios' | 'android'
        sa.Column("registered_at", sa.Text, nullable=False),
        sa.UniqueConstraint("user_id", "token", name="uq_device_push_tokens_user_token"),
    )
    op.create_index("ix_device_push_tokens_user_id", "device_push_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_device_push_tokens_user_id", "device_push_tokens")
    op.drop_table("device_push_tokens")
