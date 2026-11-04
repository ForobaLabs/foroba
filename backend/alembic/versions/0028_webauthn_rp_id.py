"""webauthn_credentials.rp_id — detect passkeys registered under a previous RP ID.

A WebAuthn credential only works for the RP ID it was created under. When the RP ID moves
(foroba-app.duckdns.org -> forobalabs.com) old credentials can never verify, so the app must
know which ones are stale. Existing rows are backfilled with the RP ID this deploy runs with
(WEBAUTHN_RP_ID, default "localhost"). Mirrors db.init_schema.

Revision ID: 0028_webauthn_rp_id
Revises: 0027_consent_unique
"""

from __future__ import annotations

import os

import sqlalchemy as sa

from alembic import op

revision = "0028_webauthn_rp_id"
down_revision = "0027_consent_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(webauthn_credentials)"))}
    if "rp_id" not in cols:
        op.execute("ALTER TABLE webauthn_credentials ADD COLUMN rp_id TEXT")
    conn.execute(
        sa.text("UPDATE webauthn_credentials SET rp_id = :rp WHERE rp_id IS NULL"),
        {"rp": os.environ.get("WEBAUTHN_RP_ID", "localhost")},
    )


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
