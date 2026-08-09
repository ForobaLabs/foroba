"""CL-2.4 — security audit event log (GDPR art.32 / NIS2, foroba#241)."""

from alembic import op

revision = "0019_security_log"
down_revision = "0018_dsar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS security_events ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " user_id INTEGER,"
        " event TEXT NOT NULL,"
        " detail TEXT,"
        " ip TEXT,"
        " created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )


def downgrade() -> None:
    raise NotImplementedError("forward-only migration")
