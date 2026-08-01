"""Admin-only backup/restore of Foroba's own critical files (TI-A, foroba#151).

Exports the SQLite identity DB + the RSA JWT keypair as a tar.gz. Import
validates the archive only contains the exact expected filenames (whitelist —
also the path-traversal guard), takes a timestamped safety copy of whatever is
currently on disk, then atomically replaces each file.
"""

from __future__ import annotations

import io
import os
import tarfile
import time
from pathlib import Path

from config import settings

_DB_ARCNAME = "foroba_identity.db"
_PRIVATE_KEY_ARCNAME = "jwt_private.pem"
_PUBLIC_KEY_ARCNAME = "jwt_public.pem"


def _file_map() -> dict[str, Path]:
    return {
        _DB_ARCNAME: Path(settings.auth_db_path).resolve(),
        _PRIVATE_KEY_ARCNAME: Path(settings.jwt_private_key_path).resolve(),
        _PUBLIC_KEY_ARCNAME: Path(settings.jwt_public_key_path).resolve(),
    }


def export_archive() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for arcname, path in _file_map().items():
            if path.is_file():
                tar.add(path, arcname=arcname)
    return buf.getvalue()


def import_archive(data: bytes) -> dict:
    file_map = _file_map()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            if member.name not in file_map:
                raise ValueError(f"Unexpected file in archive: {member.name!r}")
            if not member.isfile():
                raise ValueError(f"Unexpected non-file entry: {member.name!r}")
        extracted = {m.name: tar.extractfile(m).read() for m in members}

    restored: list[str] = []
    timestamp = int(time.time())
    for arcname, content in extracted.items():
        target = file_map[arcname]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            backup_path = target.with_name(f"{target.name}.pre-restore-{timestamp}.bak")
            backup_path.write_bytes(target.read_bytes())
        tmp_path = target.with_name(target.name + ".tmp")
        tmp_path.write_bytes(content)
        os.replace(tmp_path, target)
        restored.append(arcname)
    return {"restored_files": restored, "restart_required": True}
