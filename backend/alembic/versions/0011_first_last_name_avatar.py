"""users.first_name, users.last_name, users.avatar_url (suite identity, shared Topbar)

Suite identity plan (2026-07-25-suite-identity-plan1-foroba-backend-shared-ui.md):
- first_name/last_name: split out of `name` for use in the shared @foroba/ui Topbar
  UserMenu across Foroba/Pazuru/Tsumi. Existing users are backfilled by splitting
  their current `name` on the first space.
- avatar_url: optional, set via POST /auth/me/avatar; NULL means show initials.
"""
from __future__ import annotations

from sqlalchemy import text

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
    op.execute("ALTER TABLE users ADD COLUMN last_name TEXT")
    op.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")

    conn = op.get_bind()
    rows = conn.execute(text("SELECT id, name FROM users")).fetchall()
    for row in rows:
        parts = (row.name or "").strip().split(" ", 1)
        first = parts[0]
        last = parts[1] if len(parts) > 1 else ""
        conn.execute(
            text("UPDATE users SET first_name = :first, last_name = :last WHERE id = :id"),
            {"first": first, "last": last, "id": row.id},
        )


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
