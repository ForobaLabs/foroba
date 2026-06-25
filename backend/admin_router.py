"""Admin endpoints — feature flags and user list (admin-only).

Public endpoint /jeli/admin/settings is unauthenticated so Pazuru/Tsumi can poll it.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth.conn import get_conn
from auth.dependencies import get_current_user, require_admin
from auth import repository as repo
from auth.models import UserPublic
from settings_store import DEFAULT_SETTINGS, get_all, set_value

router = APIRouter(tags=["admin"])


class SettingPatch(BaseModel):
    value: str


@router.get("/admin/settings")
def admin_get_settings(
    conn: sqlite3.Connection = Depends(get_conn),
    _: dict = Depends(require_admin),
) -> dict[str, str]:
    return get_all(conn)


@router.patch("/admin/settings/{key}")
def admin_patch_setting(
    key: str,
    body: SettingPatch,
    conn: sqlite3.Connection = Depends(get_conn),
    _: dict = Depends(require_admin),
) -> dict[str, str]:
    if key not in DEFAULT_SETTINGS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown key: {key!r}")
    if body.value not in ("true", "false"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "value must be 'true' or 'false'")
    set_value(conn, key, body.value)
    return get_all(conn)


@router.get("/admin/users", response_model=list[UserPublic])
def admin_get_users(
    conn: sqlite3.Connection = Depends(get_conn),
    _: dict = Depends(require_admin),
) -> list[dict]:
    return repo.list_all_users(conn)


@router.get("/jeli/admin/settings")
def public_get_settings(conn: sqlite3.Connection = Depends(get_conn)) -> dict[str, str]:
    """Unauthenticated read — for Pazuru/Tsumi SettingsCache polling."""
    return get_all(conn)
