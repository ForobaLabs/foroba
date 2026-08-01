"""users.birth_year, users.country (optional profile fields) + onboarding_completed_at

New-user onboarding plan (2026-07-24-new-user-onboarding-and-connectors-plan.md):
- birth_year/country: optional fields collected at registration, never required.
- onboarding_completed_at: NULL until the post-registration guided setup (bank -> Tsumi
  investments) is finished or skipped. Existing users are backfilled to "already done"
  so they never see the new onboarding flow.
"""

from __future__ import annotations

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN birth_year INTEGER")
    op.execute("ALTER TABLE users ADD COLUMN country VARCHAR(2)")
    op.execute("ALTER TABLE users ADD COLUMN onboarding_completed_at TEXT")
    op.execute("UPDATE users SET onboarding_completed_at = datetime('now')")


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
