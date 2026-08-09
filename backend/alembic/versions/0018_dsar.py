"""CL-2.2 DSAR: restriction/objection flags + manual DSAR tracking log."""

from alembic import op

revision = "0018_dsar"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN processing_restricted INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE users ADD COLUMN marketing_objection INTEGER NOT NULL DEFAULT 0")
    op.execute(
        "CREATE TABLE IF NOT EXISTS dsar_requests ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " user_id INTEGER NOT NULL REFERENCES users(id),"
        " kind TEXT NOT NULL,"
        " status TEXT NOT NULL DEFAULT 'open',"
        " created_at TEXT NOT NULL DEFAULT (datetime('now')),"
        " resolved_at TEXT,"
        " note TEXT)"
    )


def downgrade() -> None:
    raise NotImplementedError("forward-only migration")
