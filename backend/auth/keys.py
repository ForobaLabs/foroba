"""RSA keypair for suite-wide JWT signing (RS256 migration, foroba#149).

Foroba is the ONLY service that ever holds the private key — it is generated once on
first startup and persisted to disk. Pazuru/Tsumi never see the private key; they verify
tokens using the public key exposed at GET /.well-known/jwks.json (see main.py).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _generate_keypair() -> tuple[bytes, bytes]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def load_or_generate_keypair(private_path: Path, public_path: Path) -> tuple[str, str, str]:
    """Return (private_key_pem, public_key_pem, kid). Generates + persists on first call."""
    private_path = Path(private_path)
    public_path = Path(public_path)
    if private_path.exists() and public_path.exists():
        private_pem = private_path.read_bytes()
        public_pem = public_path.read_bytes()
    else:
        private_pem, public_pem = _generate_keypair()
        private_path.parent.mkdir(parents=True, exist_ok=True)
        public_path.parent.mkdir(parents=True, exist_ok=True)
        private_path.write_bytes(private_pem)
        public_path.write_bytes(public_pem)
        private_path.chmod(0o600)
    kid = hashlib.sha256(public_pem).hexdigest()[:16]
    return private_pem.decode(), public_pem.decode(), kid


_cached: tuple[str, str, str] | None = None


def get_keypair(settings) -> tuple[str, str, str]:
    """Process-wide cached keypair, loaded from settings.jwt_private_key_path /
    settings.jwt_public_key_path on first call."""
    global _cached
    if _cached is None:
        _cached = load_or_generate_keypair(
            Path(settings.jwt_private_key_path), Path(settings.jwt_public_key_path)
        )
    return _cached
