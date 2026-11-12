"""Suite-level backup orchestrator (TI-A, foroba#151).

Bundles Foroba's own export (backup_service.export_archive) with Pazuru's and
Tsumi's /admin/backup/export responses into one outer tar + manifest.json,
encrypted with a passphrase-derived key (scrypt -> Fernet). Restore reverses
this: decrypt, restore Foroba locally, forward the other 2 sub-archives to
their own /admin/backup/import endpoints.

Output format: 16-byte random salt (raw bytes) followed by a Fernet token.
The passphrase is never logged or persisted — used only in-memory to derive
the key for the duration of a single request.
"""

from __future__ import annotations

import base64
import io
import json
import os
import tarfile
import time
from datetime import UTC, datetime

import httpx
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from backup_service import export_archive, import_archive
from config import settings

_SALT_LEN = 16
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


class InvalidPassphrase(Exception):
    pass


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))


def _encrypt(data: bytes, passphrase: str) -> bytes:
    salt = os.urandom(_SALT_LEN)
    key = _derive_key(passphrase, salt)
    token = Fernet(key).encrypt(data)
    return salt + token


def decrypt_archive(encrypted: bytes, passphrase: str) -> bytes:
    salt, token = encrypted[:_SALT_LEN], encrypted[_SALT_LEN:]
    key = _derive_key(passphrase, salt)
    try:
        return Fernet(key).decrypt(token)
    except InvalidToken as err:
        raise InvalidPassphrase("Wrong passphrase or corrupted archive") from err


async def _fetch_export(
    client: httpx.AsyncClient, base_url: str, cookie: str, stepup_token: str | None = None
) -> bytes:
    resp = await client.get(
        f"{base_url}/admin/backup/export",
        cookies={"suite_session": cookie},
        headers={"X-Stepup-Token": stepup_token} if stepup_token else {},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.content


async def _post_import(
    client: httpx.AsyncClient,
    base_url: str,
    cookie: str,
    data: bytes,
    stepup_token: str | None = None,
) -> dict:
    resp = await client.post(
        f"{base_url}/admin/backup/import",
        cookies={"suite_session": cookie},
        headers={"X-Stepup-Token": stepup_token} if stepup_token else {},
        files={"file": ("backup.tar.gz", data, "application/gzip")},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


async def export_suite(passphrase: str, cookie: str, stepup: dict[str, str] | None = None) -> bytes:
    """`stepup` maps app name -> app-scoped step-up token; Pazuru/Tsumi answer 428
    to admin backup export without one."""
    foroba_blob = export_archive()
    async with httpx.AsyncClient() as client:
        pazuru_blob = await _fetch_export(
            client, settings.pazuru_api_url, cookie, (stepup or {}).get("pazuru")
        )
        tsumi_blob = await _fetch_export(
            client, settings.tsumi_api_url, cookie, (stepup or {}).get("tsumi")
        )

    manifest = json.dumps(
        {
            "exported_at": datetime.now(UTC).isoformat(),
            "apps": ["foroba", "pazuru", "tsumi"],
        }
    ).encode()

    outer = io.BytesIO()
    with tarfile.open(fileobj=outer, mode="w") as tar:
        for arcname, content in (
            ("manifest.json", manifest),
            ("foroba.tar.gz", foroba_blob),
            ("pazuru.tar.gz", pazuru_blob),
            ("tsumi.tar.gz", tsumi_blob),
        ):
            info = tarfile.TarInfo(name=arcname)
            info.size = len(content)
            info.mtime = int(time.time())
            tar.addfile(info, io.BytesIO(content))

    return _encrypt(outer.getvalue(), passphrase)


async def import_suite(
    encrypted: bytes, passphrase: str, cookie: str, stepup: dict[str, str] | None = None
) -> dict:
    outer_bytes = decrypt_archive(encrypted, passphrase)
    with tarfile.open(fileobj=io.BytesIO(outer_bytes), mode="r:") as tar:
        names = set(tar.getnames())
        required = {"manifest.json", "foroba.tar.gz", "pazuru.tar.gz", "tsumi.tar.gz"}
        if not required.issubset(names):
            raise ValueError(f"Archive missing expected entries: {required - names}")
        blobs = {name: tar.extractfile(name).read() for name in required if name != "manifest.json"}

    result: dict = {}
    result["foroba"] = import_archive(blobs["foroba.tar.gz"])

    async with httpx.AsyncClient() as client:
        for app_name, base_url in (
            ("pazuru", settings.pazuru_api_url),
            ("tsumi", settings.tsumi_api_url),
        ):
            try:
                result[app_name] = await _post_import(
                    client,
                    base_url,
                    cookie,
                    blobs[f"{app_name}.tar.gz"],
                    (stepup or {}).get(app_name),
                )
            except (httpx.HTTPError, RuntimeError) as exc:
                result[app_name] = {"error": str(exc)}

    return result
