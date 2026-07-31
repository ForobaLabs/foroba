"""GL-11.2: encrypt a plaintext SQLite DB file in place using SQLCipher.

Separate trust boundary from the per-column Fernet field_encryption_key
(chat_crypto.py) — this encrypts the WHOLE file.

Idempotent: if the target file is already SQLCipher-encrypted (or otherwise
unreadable as plaintext SQLite), this is a no-op. Fails loudly and does not
touch the original file unless the newly-built encrypted copy is verified to
open with the given key and match every table's row count exactly. A
plaintext backup of the pre-encryption file is left alongside the original
(in addition to whatever backup the operator already took before running
this).

Usage:
    python scripts/encrypt_db_at_rest.py <db_path> <encryption_key>
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

import sqlcipher3.dbapi2 as sqlcipher


def _is_plaintext_sqlite(db_path: str) -> bool:
    """Return True if db_path opens fine with stdlib sqlite3 (i.e. not encrypted)."""
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("SELECT count(*) FROM sqlite_master")
        conn.close()
        return True
    except sqlite3.DatabaseError:
        return False


def _table_names(conn: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]


def _row_counts(execute, tables: list[str]) -> dict[str, int]:
    return {name: execute(f"SELECT count(*) FROM {name}").fetchone()[0] for name in tables}


def encrypt_db(db_path: str, key: str) -> None:
    db_path = str(Path(db_path).resolve())

    if not _is_plaintext_sqlite(db_path):
        print(f"{db_path} is already encrypted (or unreadable as plaintext) — skipping.")
        return

    plain_conn = sqlite3.connect(db_path)
    tables = _table_names(plain_conn)
    plain_counts = _row_counts(plain_conn.execute, tables)
    plain_conn.close()

    tmp_path = db_path + ".gl11-2-encrypting.tmp"
    if Path(tmp_path).exists():
        Path(tmp_path).unlink()

    escaped_tmp = tmp_path.replace("'", "''")
    escaped_key = key.replace("'", "''")

    # Official SQLCipher migration pattern: open the plaintext file with the
    # SQLCipher-enabled driver but issue NO `PRAGMA key` on it (that throws on
    # a plaintext source) — SQLCipher reads plaintext files transparently when
    # no key is set. Then ATTACH a brand-new encrypted file and export into it.
    conn = sqlcipher.connect(db_path)
    conn.execute(f"ATTACH DATABASE '{escaped_tmp}' AS encrypted KEY '{escaped_key}'")
    conn.execute("SELECT sqlcipher_export('encrypted')")
    conn.execute("DETACH DATABASE encrypted")
    conn.close()

    verify_conn = sqlcipher.connect(tmp_path)
    verify_conn.execute(f"PRAGMA key = '{escaped_key}'")
    verify_counts = _row_counts(verify_conn.execute, tables)
    verify_conn.close()

    if verify_counts != plain_counts:
        Path(tmp_path).unlink()
        raise RuntimeError(
            f"Row count mismatch after encryption: plaintext={plain_counts} "
            f"encrypted={verify_counts}. Aborting — original file untouched."
        )

    backup_path = db_path + ".gl11-2-preencrypt.bak"
    shutil.copy2(db_path, backup_path)
    Path(tmp_path).replace(db_path)
    print(f"Encrypted {db_path} in place. Pre-encryption plaintext copy: {backup_path}")
    print(f"Verified row counts match: {verify_counts}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: encrypt_db_at_rest.py <db_path> <encryption_key>", file=sys.stderr)
        sys.exit(1)
    encrypt_db(sys.argv[1], sys.argv[2])
