from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from auth.security import create_token, decode_token


def _keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


PRIVATE_KEY, PUBLIC_KEY = _keypair()


def test_create_token_includes_claims():
    token = create_token(
        42,
        PRIVATE_KEY,
        60,
        tier="premium",
        audience="expert",
        is_admin=True,
    )
    claims = decode_token(token, PUBLIC_KEY)
    assert claims["sub"] == "42"
    assert claims["tier"] == "premium"
    assert claims["audience"] == "expert"
    assert claims["is_admin"] is True


def test_create_token_default_claims():
    """No kwargs — verifies signature defaults are tier=free, audience=base, is_admin=False."""
    token = create_token(1, PRIVATE_KEY, 60)
    claims = decode_token(token, PUBLIC_KEY)
    assert claims["tier"] == "free"
    assert claims["audience"] == "base"
    assert claims["is_admin"] is False
