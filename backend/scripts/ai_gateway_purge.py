"""Plan AV T7: retry AI-gateway erasures deferred when the gateway was down at account deletion.

Run from the backend directory (cron or by hand):
    python scripts/ai_gateway_purge.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
from ai_gateway_client import get_client, list_pending_deletes, purge_pending
from config import settings


def main() -> int:
    conn = db.connect(settings.auth_db_path)
    pending = len(list_pending_deletes(conn))
    done, failed = asyncio.run(purge_pending(conn, get_client()))
    print(f"ai_gateway_purge pending={pending} done={done} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
