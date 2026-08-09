from config import settings


def test_access_token_ttl_defaults_to_15_minutes():
    assert settings.access_token_ttl_minutes == 15


def test_refresh_token_ttl_defaults_to_30_days():
    assert settings.refresh_token_ttl_days == 30
