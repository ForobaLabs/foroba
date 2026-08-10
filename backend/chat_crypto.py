"""Fernet encryption for Jeli Lab chat history stored at rest (GL-11.3).

`sandbox_conversations.content`/`code` in `db.py` are plain `sqlite3` columns
(no ORM), so — unlike Pazuru's `services/token_crypto.EncryptedString`
TypeDecorator — encryption/decryption here is applied explicitly by the
call sites in `db.py::save_sandbox_turn`/`get_sandbox_history`, not
transparently by a column type.

FIELD_ENCRYPTION_KEY must be a urlsafe-base64 32-byte key. Generate once with:
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from config import settings


def _fernet() -> Fernet:
    if not settings.field_encryption_key:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY is not set. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return Fernet(settings.field_encryption_key.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()


def is_encrypted(value: str) -> bool:
    """True if `value` already decrypts with the current key (idempotent migration guard)."""
    try:
        _fernet().decrypt(value.encode())
        return True
    except (InvalidToken, ValueError):
        return False


def safe_encrypt(plaintext: str | None) -> str | None:
    """Encrypt if FIELD_ENCRYPTION_KEY is configured; return plaintext otherwise. None-safe."""
    if plaintext is None or not settings.field_encryption_key:
        return plaintext
    return encrypt(plaintext)


def safe_decrypt(ciphertext: str | None) -> str | None:
    """Decrypt if key is set and value looks encrypted; return as-is otherwise. None-safe.

    Migration-safe: legacy plaintext values (stored before encryption was enabled) are
    returned unchanged so callers never receive garbled data after the feature is enabled.
    """
    if ciphertext is None or not settings.field_encryption_key:
        return ciphertext
    return decrypt(ciphertext) if is_encrypted(ciphertext) else ciphertext
