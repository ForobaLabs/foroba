"""API key management endpoints — issue/list/revoke personal API keys (foroba#165,
TI-D item 5, Plan A)."""

from __future__ import annotations

import secrets
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

import db
from auth.conn import get_conn
from auth.dependencies import get_current_user
from auth.security import hash_password

router = APIRouter(prefix="/auth/api-keys", tags=["api-keys"])


class ApiKeyCreate(BaseModel):
    label: str


class ApiKeyOut(BaseModel):
    id: int
    label: str
    key_prefix: str
    is_active: bool
    last_used_at: str | None
    created_at: str


class ApiKeyCreated(ApiKeyOut):
    key: str  # "prefix.secret" — shown once, never retrievable again


def _to_out(row: sqlite3.Row) -> ApiKeyOut:
    return ApiKeyOut(
        id=row["id"],
        label=row["label"],
        key_prefix=row["key_prefix"],
        is_active=bool(row["is_active"]),
        last_used_at=row["last_used_at"],
        created_at=row["created_at"],
    )


@router.post("", response_model=ApiKeyCreated, status_code=201)
def create_api_key(
    body: ApiKeyCreate,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> ApiKeyCreated:
    secret = secrets.token_urlsafe(32)
    prefix = "fpk_" + secrets.token_hex(6)
    row = db.create_api_key(
        conn,
        user_id=user["id"],
        label=body.label,
        key_prefix=prefix,
        secret_hash=hash_password(secret),
    )
    return ApiKeyCreated(**_to_out(row).model_dump(), key=f"{prefix}.{secret}")


@router.get("", response_model=list[ApiKeyOut])
def list_api_keys(
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[ApiKeyOut]:
    return [_to_out(r) for r in db.list_api_keys(conn, user_id=user["id"])]


@router.delete("/{key_id}", status_code=204)
def revoke_api_key(
    key_id: int,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    if not db.revoke_api_key(conn, key_id, user_id=user["id"]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
