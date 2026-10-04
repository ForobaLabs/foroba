"""consents: unique (user_id, document_type, document_version) — AI-4-F4.

Accepting the same document version twice used to append a duplicate row (the re-consent
screen was submitted up to 5x). Drops the redundant copies (keeping the earliest, which holds
the first-acceptance timestamp) and enforces uniqueness. Mirrors db.init_schema.

Revision ID: 0027_consent_unique
Revises: 0026_waitlist
"""

from __future__ import annotations

from alembic import op

revision = "0027_consent_unique"
down_revision = "0026_waitlist"
branch_labels = None
depends_on = None

# Same statements as db.CONSENT_DEDUPE_SQL / CONSENT_UNIQUE_INDEX_SQL (kept inline: migrations
# must not import application modules).
_DEDUPE = (
    "DELETE FROM consents WHERE id NOT IN ("
    "SELECT MIN(id) FROM consents GROUP BY user_id, document_type, document_version)"
)
_UNIQUE = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_consents_user_doc_version "
    "ON consents(user_id, document_type, document_version)"
)


def upgrade() -> None:
    op.execute(_DEDUPE)
    op.execute(_UNIQUE)


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
