import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from auth.security import create_token, decode_token, hash_password, needs_rehash, verify_password


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
OTHER_PRIVATE_KEY, OTHER_PUBLIC_KEY = _keypair()


def test_hash_and_verify_roundtrip():
    h = hash_password("s3cret!")
    assert h != "s3cret!"
    assert verify_password("s3cret!", h) is True
    assert verify_password("wrong", h) is False


def test_hash_and_verify_argon2():
    h = hash_password("secret123")
    assert h.startswith("$argon2")
    assert verify_password("secret123", h) is True
    assert verify_password("wrong", h) is False


def test_verify_legacy_bcrypt():
    import bcrypt as _bcrypt

    legacy = _bcrypt.hashpw(b"secret123", _bcrypt.gensalt()).decode()
    assert verify_password("secret123", legacy) is True
    assert verify_password("wrong", legacy) is False
    assert needs_rehash(legacy) is True


def test_needs_rehash_argon2_is_false():
    h = hash_password("secret")
    assert needs_rehash(h) is False


def test_token_roundtrip_contains_subject():
    token = create_token(user_id=42, private_key=PRIVATE_KEY, ttl_minutes=60)
    claims = decode_token(token, public_key=PUBLIC_KEY)
    assert claims["sub"] == "42"


def test_token_rejects_wrong_key():
    token = create_token(user_id=1, private_key=PRIVATE_KEY, ttl_minutes=60)
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token, public_key=OTHER_PUBLIC_KEY)


def test_token_rejects_expired():
    token = create_token(user_id=1, private_key=PRIVATE_KEY, ttl_minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token, public_key=PUBLIC_KEY)


# ── Pre-beta Task 2.2 row 9: algorithm pinning and mandatory expiry ──


def _forge(payload: dict, key: str, algorithm: str) -> str:
    return jwt.encode(payload, key, algorithm=algorithm)


def test_token_rejects_alg_none():
    token = _forge({"sub": "1", "exp": 4_102_444_800}, None, "none")
    with pytest.raises(jwt.PyJWTError):
        decode_token(token, PUBLIC_KEY)


def test_token_rejects_hs256_signed_with_the_public_key():
    """Classic RS256→HS256 confusion: the public key used as an HMAC secret."""
    import hashlib
    import hmac
    import json
    from base64 import urlsafe_b64encode

    def b64(raw: bytes) -> str:
        return urlsafe_b64encode(raw).rstrip(b"=").decode()

    head = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = b64(json.dumps({"sub": "1", "exp": 4_102_444_800}).encode())
    sig = hmac.new(PUBLIC_KEY.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest()
    with pytest.raises(jwt.PyJWTError):
        decode_token(f"{head}.{body}.{b64(sig)}", PUBLIC_KEY)


def test_token_without_exp_is_rejected():
    token = _forge({"sub": "1"}, PRIVATE_KEY, "RS256")
    with pytest.raises(jwt.PyJWTError):
        decode_token(token, PUBLIC_KEY)
