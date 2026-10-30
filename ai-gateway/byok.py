"""Write-only BYOK vault: keys are Fernet-encrypted at rest and never returned after save."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, SecretStr

import db
from auth import Caller, require_caller
from config import get_settings
from providers import openai_compat
from providers.base import ChatRequest, ProviderError
from providers.registry import PROVIDERS

router = APIRouter(prefix="/v1/byok", tags=["byok"])


class KeyNotFound(Exception):
    pass


@dataclass(frozen=True)
class KeyInfo:
    provider: str
    last4: str
    model: str
    status: str
    created_at: str


def _fernet() -> Fernet:
    return Fernet(get_settings().field_key.encode())


def _info(row) -> KeyInfo:
    return KeyInfo(row["provider"], row["last4"], row["model"], row["status"], row["created_at"])


def _fail(code: str, status: int = 422) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code})


async def _probe(provider: str, api_key: str, account_id: str | None, model: str) -> None:
    await openai_compat.complete(
        PROVIDERS[provider],
        api_key,
        account_id,
        ChatRequest(messages=[{"role": "user", "content": "ping"}], model=model, max_tokens=1),
    )


async def save(
    conn, user_id: int, provider: str, api_key: str, account_id: str | None, model: str
) -> KeyInfo:
    spec = PROVIDERS.get(provider)
    if spec is None:
        raise _fail("unknown_provider")
    if model not in spec.models:
        raise _fail("unknown_model")
    if spec.needs_account_id and not account_id:
        raise _fail("account_id_required")
    try:
        await _probe(provider, api_key, account_id, model)
    except ProviderError:
        raise _fail("byok_test_failed") from None
    f = _fernet()
    conn.execute(
        "INSERT INTO byok_keys(user_id, provider, secret_enc, account_id_enc, last4, model, "
        "status, created_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(user_id, provider) DO UPDATE SET "
        "secret_enc=excluded.secret_enc, account_id_enc=excluded.account_id_enc, "
        "last4=excluded.last4, model=excluded.model, status='ok', created_at=excluded.created_at",
        (
            user_id,
            provider,
            f.encrypt(api_key.encode()),
            f.encrypt(account_id.encode()) if account_id else None,
            api_key[-4:],
            model,
            "ok",
            datetime.now(UTC).isoformat(),
        ),
    )
    conn.commit()
    return _info(
        conn.execute(
            "SELECT * FROM byok_keys WHERE user_id=? AND provider=?", (user_id, provider)
        ).fetchone()
    )


def list_keys(conn, user_id: int) -> list[KeyInfo]:
    rows = conn.execute(
        "SELECT * FROM byok_keys WHERE user_id=? ORDER BY provider", (user_id,)
    ).fetchall()
    return [_info(r) for r in rows]


def delete(conn, user_id: int, provider: str) -> None:
    conn.execute("DELETE FROM byok_keys WHERE user_id=? AND provider=?", (user_id, provider))
    conn.execute(
        "UPDATE ai_prefs SET provider='local', byok_provider=NULL, updated_at=? "
        "WHERE user_id=? AND provider='byok' AND byok_provider=?",
        (datetime.now(UTC).isoformat(), user_id, provider),
    )
    conn.commit()


def load_key(conn, user_id: int, provider: str) -> tuple[str, str | None, str]:
    """Return (api_key, account_id, model) or raise KeyNotFound."""
    row = conn.execute(
        "SELECT secret_enc, account_id_enc, model FROM byok_keys WHERE user_id=? AND provider=?",
        (user_id, provider),
    ).fetchone()
    if row is None:
        raise KeyNotFound(provider)
    f = _fernet()
    account = f.decrypt(bytes(row["account_id_enc"])).decode() if row["account_id_enc"] else None
    return f.decrypt(bytes(row["secret_enc"])).decode(), account, row["model"]


def mark_invalid(conn, user_id: int, provider: str) -> None:
    _set_status(conn, user_id, provider, "invalid")


def _set_status(conn, user_id: int, provider: str, status: str) -> None:
    conn.execute(
        "UPDATE byok_keys SET status=? WHERE user_id=? AND provider=?",
        (status, user_id, provider),
    )
    conn.commit()


class KeyIn(BaseModel):
    provider: str
    api_key: SecretStr
    account_id: str | None = None
    model: str


@router.get("")
def list_route(caller: Caller = Depends(require_caller), conn=Depends(db.get_conn)):  # noqa: B008
    return [asdict(k) for k in list_keys(conn, caller.user_id)]


@router.put("")
async def put_route(
    body: KeyIn, caller: Caller = Depends(require_caller), conn=Depends(db.get_conn)  # noqa: B008
):
    info = await save(
        conn, caller.user_id, body.provider, body.api_key.get_secret_value(), body.account_id, body.model
    )
    return asdict(info)


@router.delete("/{provider}", status_code=204)
def delete_route(
    provider: str, caller: Caller = Depends(require_caller), conn=Depends(db.get_conn)  # noqa: B008
):
    delete(conn, caller.user_id, provider)
    return Response(status_code=204)


@router.post("/{provider}/test")
async def test_route(
    provider: str, caller: Caller = Depends(require_caller), conn=Depends(db.get_conn)  # noqa: B008
):
    try:
        key, account_id, model = load_key(conn, caller.user_id, provider)
    except KeyNotFound:
        raise HTTPException(status_code=404, detail={"code": "byok_not_found"}) from None
    try:
        await _probe(provider, key, account_id, model)
    except ProviderError as exc:
        if exc.kind == "auth":
            mark_invalid(conn, caller.user_id, provider)
            return {"ok": False, "status": "invalid"}
        return {"ok": False, "status": "unreachable"}
    _set_status(conn, caller.user_id, provider, "ok")
    return {"ok": True, "status": "ok"}
