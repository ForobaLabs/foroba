"""Offsite upload of the encrypted suite backup to Cloudflare R2 (TI-E, foroba#172).

R2 is S3-compatible, so this uses `boto3`'s standard S3 client pointed at R2's
endpoint. The uploaded bytes are always already-encrypted (produced by
`backup_orchestrator.export_suite()`) — this module never sees plaintext.

No-ops when unconfigured, following the same convention as `GLITCHTIP_DSN`: an
empty `.env` means the feature is simply off, not an error.
"""

from __future__ import annotations

from datetime import UTC, datetime

import boto3

from config import settings


def is_configured() -> bool:
    return bool(
        settings.r2_account_id
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
        and settings.r2_bucket
        and settings.backup_encryption_passphrase
    )


def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
    )


def upload_backup(data: bytes) -> str:
    """Upload the encrypted archive, returning the object key. Raises on failure —
    this is a scheduled write path, errors must surface (caught by the caller's
    logging + GlitchTip), never be swallowed."""
    key = f"backups/suite-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.bin"
    _client().put_object(Bucket=settings.r2_bucket, Key=key, Body=data)
    return key
