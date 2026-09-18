"""users.session_version column (XAPP-D03).

POST /logout only cleared the local suite_session cookie and best-effort
revoked future refresh-token re-issuance -- it never touched the already-
issued suite_session JWT itself, which stayed valid (per its own `exp`
claim) until natural expiry. Live-confirmed in this program: replaying an
old suite_session via `Authorization: Bearer` after logout still returned
200 from Pazuru's GET /api/accounts.

This column is a per-user monotonically-increasing counter embedded in
every freshly-issued suite_session JWT as a `session_version` claim.
Logout bumps it and best-effort pushes the new floor to Pazuru/Tsumi
(auth/session_invalidation.py), which each keep an in-memory floor cache
checked on every authenticated request -- any JWT whose claim is below the
recorded floor is rejected with 401, immediately invalidating every
already-issued token for that user without needing a token blocklist.

Revision ID: 0024_session_version
Revises: 0023_totp_secret_pending
"""

from __future__ import annotations

from alembic import op

revision = "0024_session_version"
down_revision = "0023_totp_secret_pending"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1")


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
