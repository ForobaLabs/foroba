"""fx_rates table (TI-D item 3 Plan 3, foroba#164)"""

from __future__ import annotations

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS fx_rates (
            currency TEXT NOT NULL,
            rate_to_eur REAL NOT NULL,
            rate_date TEXT NOT NULL,
            fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (currency, rate_date)
        )
        """
    )


def downgrade() -> None:
    raise NotImplementedError("forward-only — see spec Non-goals")
