import pytest

from stepup import (
    StepupTokenError,
    issue_stepup_cookies,
    issue_stepup_token,
    needs_refresh,
    verify_stepup_token,
)


def test_issue_and_verify_round_trip():
    token = issue_stepup_token(user_id=42, app="pazuru")
    claims = verify_stepup_token(token, expected_app="pazuru")
    assert claims["sub"] == "42"
    assert claims["app"] == "pazuru"


def test_verify_rejects_wrong_app_claim():
    token = issue_stepup_token(user_id=42, app="pazuru")
    with pytest.raises(StepupTokenError):
        verify_stepup_token(token, expected_app="tsumi")


def test_verify_rejects_garbage_token():
    with pytest.raises(StepupTokenError):
        verify_stepup_token("not-a-jwt", expected_app="pazuru")


def test_needs_refresh_true_when_near_expiry(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "stepup_ttl_minutes", 1)
    monkeypatch.setattr(settings, "stepup_refresh_threshold_minutes", 1)
    token = issue_stepup_token(user_id=42, app="pazuru")
    claims = verify_stepup_token(token, expected_app="pazuru")
    assert needs_refresh(claims) is True


def test_needs_refresh_false_when_freshly_issued():
    token = issue_stepup_token(user_id=42, app="pazuru")
    claims = verify_stepup_token(token, expected_app="pazuru")
    assert needs_refresh(claims) is False


def test_issue_stepup_cookies_mints_both_apps():
    """foroba#215: callers with no interactive session (background jobs, API-key
    requests) mint both stepup cookies directly."""
    cookies = issue_stepup_cookies(user_id=42)
    assert set(cookies) == {"pazuru", "tsumi"}
    pazuru_claims = verify_stepup_token(cookies["pazuru"], expected_app="pazuru")
    tsumi_claims = verify_stepup_token(cookies["tsumi"], expected_app="tsumi")
    assert pazuru_claims["sub"] == "42"
    assert tsumi_claims["sub"] == "42"


def test_verify_rejects_stepup_token_without_exp():
    """Pre-beta Task 2.2 row 9: a step-up token must carry an expiry."""
    import jwt

    from auth import keys
    from config import settings

    private_key, _, kid = keys.get_keypair(settings)
    token = jwt.encode(
        {"sub": "42", "app": "pazuru", "typ": "stepup"},
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )
    with pytest.raises(StepupTokenError):
        verify_stepup_token(token, expected_app="pazuru")
