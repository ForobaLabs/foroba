"""email_otp_codes.failed_attempts — cap wrong guesses per outstanding email code.

Five wrong guesses void the code (pre-beta Task 2.2). Mirrors db.init_schema.

Revision ID: 0030_email_otp_attempts
Revises: 0029_users_is_synthetic
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0030_email_otp_attempts"
down_revision = "0029_users_is_synthetic"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(email_otp_codes)"))}
    if "failed_attempts" not in cols:
        op.execute(
            "ALTER TABLE email_otp_codes ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0"
        )


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
