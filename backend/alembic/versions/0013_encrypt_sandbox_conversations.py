"""encrypt sandbox_conversations.content/code at rest (GL-11.3, foroba#192)

Re-encrypts existing plaintext values in sandbox_conversations.content/code with
Fernet (chat_crypto.encrypt), so the SQLite file only ever holds ciphertext for
these columns going forward. Idempotent: any row whose value already decrypts
successfully with the current FIELD_ENCRYPTION_KEY is left untouched (safe to
re-run). Mirrors pazuru/backend/alembic/versions/0008_encrypt_sensitive_fields.py.

This is a data-only migration (no schema change) — db.py::save_sandbox_turn/
get_sandbox_history already encrypt/decrypt transparently at the call sites
(no ORM TypeDecorator here, since this table uses raw sqlite3, not SQLAlchemy).

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-31 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from chat_crypto import encrypt, is_encrypted

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

_TARGETS = ["content", "code"]


def upgrade() -> None:
    bind = op.get_bind()
    for column in _TARGETS:
        rows = bind.execute(
            sa.text(f"SELECT id, {column} FROM sandbox_conversations")
        ).fetchall()
        for row_id, value in rows:
            if value is None or is_encrypted(value):
                continue
            bind.execute(
                sa.text(
                    f"UPDATE sandbox_conversations SET {column} = :val WHERE id = :id"
                ),
                {"val": encrypt(value), "id": row_id},
            )


def downgrade() -> None:
    raise NotImplementedError("forward-only — restore from a pre-migration backup if needed")
