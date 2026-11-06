"""Pre-beta Task 0.4: create or delete synthetic test identities (is_synthetic=1).

Run from the backend directory (the owner runs it in production; Claude never does):
    python scripts/provision_synthetic.py --count 6 --prefix beta-synth --out <file>
    python scripts/provision_synthetic.py --delete --prefix lt

Users get the address <prefix>-<n>@forobalabs.com and a random password. Profiles repeat in
blocks of six: base/free, base/premium, expert/free, expert/premium, then a household owner
(base/premium) and its member (base/free). Credentials go only to --out (mode 600, never
overwritten), never to stdout. --delete removes Foroba rows of flagged users with that prefix
only; Pazuru/Tsumi rows keyed by those ids are not touched.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth import repository as repo
from auth.security import hash_password

DOMAIN = "forobalabs.com"
# (audience, tier, household role)
PROFILES = [
    ("base", "free", None),
    ("base", "premium", None),
    ("expert", "free", None),
    ("expert", "premium", None),
    ("base", "premium", "owner"),
    ("base", "free", "member"),
]


def provision(conn: sqlite3.Connection, count: int, prefix: str) -> list[tuple[str, str, str]]:
    """Create `count` flagged users; return (email, password, profile) for each one created."""
    created: list[tuple[str, str, str]] = []
    for n in range(1, count + 1):
        email = f"{prefix}-{n}@{DOMAIN}"
        if repo.get_user_by_email(conn, email):
            continue
        audience, tier, role = PROFILES[(n - 1) % len(PROFILES)]
        password = secrets.token_urlsafe(18)
        user = repo.create_user(
            conn,
            email=email,
            name=f"Synthetic {prefix} {n}",
            password_hash=hash_password(password),
            tier=tier,
            audience=audience,
        )
        household = f"{prefix}-hh-{(n - 1) // len(PROFILES) + 1}" if role else None
        conn.execute(
            "UPDATE users SET is_synthetic = 1, household_id = ?, "
            "onboarding_completed_at = datetime('now') WHERE id = ?",
            (household, user["id"]),
        )
        created.append(
            (email, password, f"{audience}/{tier}" + (f"/household-{role}" if role else ""))
        )
    conn.commit()
    return created


def delete(conn: sqlite3.Connection, prefix: str) -> int:
    """Delete flagged users whose address starts with `<prefix>-`; return how many."""
    rows = conn.execute(
        "SELECT id FROM users WHERE is_synthetic = 1 AND email LIKE ? ESCAPE '\\'",
        (prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "-%",),
    ).fetchall()
    for row in rows:
        repo.delete_user(conn, row[0])
    return len(rows)


def _write_secret_file(path: Path, rows: list[tuple[str, str, str]]) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.writelines(f"{email}\t{password}\t{profile}\n" for email, password, profile in rows)


def main(argv: list[str] | None = None, conn: sqlite3.Connection | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--count", type=int, default=6)
    parser.add_argument("--delete", action="store_true")
    parser.add_argument("--out", type=Path, help="credentials file to create (mode 600)")
    args = parser.parse_args(argv)

    if conn is None:
        import db
        from config import settings

        conn = db.connect(settings.auth_db_path)

    if args.delete:
        print(f"provision_synthetic deleted={delete(conn, args.prefix)} prefix={args.prefix}")
        return 0

    if args.out is None:
        parser.error("--out is required when creating users")
    if args.out.exists():
        parser.error(f"{args.out} already exists — refusing to overwrite credentials")
    created = provision(conn, args.count, args.prefix)
    _write_secret_file(args.out, created)
    print(f"provision_synthetic created={len(created)} prefix={args.prefix} out={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
