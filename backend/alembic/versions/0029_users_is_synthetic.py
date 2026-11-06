"""users.is_synthetic — flag test identities created by scripts/provision_synthetic.py.

Synthetic users (beta walkthroughs, load tests) must never count in admin KPIs or analytics.
Mirrors db.init_schema.

Revision ID: 0029_users_is_synthetic
Revises: 0028_webauthn_rp_id
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0029_users_is_synthetic"
down_revision = "0028_webauthn_rp_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(users)"))}
    if "is_synthetic" not in cols:
        op.execute("ALTER TABLE users ADD COLUMN is_synthetic INTEGER NOT NULL DEFAULT 0")


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
