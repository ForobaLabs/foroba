import time

import jwt
import pytest

from auth.security import hash_password, verify_password, create_token, decode_token


def test_hash_and_verify_roundtrip():
    h = hash_password("s3cret!")
    assert h != "s3cret!"
    assert verify_password("s3cret!", h) is True
    assert verify_password("wrong", h) is False


def test_token_roundtrip_contains_subject():
    token = create_token(user_id=42, secret="k", ttl_minutes=60)
    claims = decode_token(token, secret="k")
    assert claims["sub"] == "42"


def test_token_rejects_wrong_secret():
    token = create_token(user_id=1, secret="right", ttl_minutes=60)
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token, secret="wrong")


def test_token_rejects_expired():
    token = create_token(user_id=1, secret="k", ttl_minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token, secret="k")
