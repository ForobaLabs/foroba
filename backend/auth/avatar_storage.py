"""Avatar file storage — validates and persists profile photo uploads.

Storage directory is configurable via AVATAR_STORAGE_DIR (tests use a tmp_path;
production defaults to backend/static/avatars, served by main.py's StaticFiles mount).
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

_ALLOWED_CONTENT_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}
_MAX_BYTES = 2 * 1024 * 1024  # 2MB


def _storage_dir() -> Path:
    configured = os.getenv("AVATAR_STORAGE_DIR")
    if configured:
        path = Path(configured)
    else:
        path = Path(__file__).resolve().parent.parent / "static" / "avatars"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_avatar(user_id: int, file: UploadFile, content: bytes) -> str:
    """Validate and save an uploaded avatar. Returns the served URL path."""
    ext = _ALLOWED_CONTENT_TYPES.get(file.content_type or "")
    if ext is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Unsupported image type — use PNG, JPEG, or WebP",
        )
    if len(content) > _MAX_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Image must be 2MB or smaller")

    dest = _storage_dir() / f"{user_id}.{ext}"
    dest.write_bytes(content)
    return f"/static/avatars/{user_id}.{ext}"
