import pytest
from auth.security import create_token, decode_token

SECRET = "test-secret"

def test_create_token_includes_claims():
    token = create_token(
        42, SECRET, 60,
        tier="premium", audience="expert", is_admin=True,
    )
    claims = decode_token(token, SECRET)
    assert claims["sub"] == "42"
    assert claims["tier"] == "premium"
    assert claims["audience"] == "expert"
    assert claims["is_admin"] is True

def test_create_token_default_claims():
    token = create_token(1, SECRET, 60, tier="free", audience="base", is_admin=False)
    claims = decode_token(token, SECRET)
    assert claims["tier"] == "free"
    assert claims["audience"] == "base"
    assert claims["is_admin"] is False
