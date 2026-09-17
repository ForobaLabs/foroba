"""users.totp_secret_pending column.

FOR-D06: auth/repository.py's set_totp_secret() unconditionally wrote the new
secret into totp_secret AND flipped totp_enabled to 0 as an immediate side
effect of merely generating a secret — not gated behind the subsequent
/auth/2fa/verify call succeeding. POST /auth/2fa/enroll had no already
-enrolled guard, so revisiting /enroll on an already-MFA-enrolled account
instantly disabled MFA before the user ever saw the new QR code.

This column stages a freshly generated secret separately from the live
totp_secret column; enable_totp() (called only on a successful /verify)
atomically promotes it. set_totp_secret() no longer touches totp_enabled at
all.

Revision ID: 0023_totp_secret_pending
Revises: 0022_email_verified_household_invites
"""

from __future__ import annotations

from alembic import op

revision = "0023_totp_secret_pending"
down_revision = "0022_email_verified_household_invites"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN totp_secret_pending TEXT")


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
