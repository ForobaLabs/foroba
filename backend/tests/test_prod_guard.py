"""Plan AU M-7: production startup guard."""

import pytest

from prod_guard import check_production_config

GOOD = {
    "ENVIRONMENT": "production",
    "INTERNAL_API_TOKEN": "x" * 32,
    "ALLOWED_ORIGINS": "https://legacy.example.org",
}


def test_noop_outside_production():
    check_production_config({"AUTH_DEV_BYPASS": "true"})


def test_good_production_config_passes():
    check_production_config(GOOD, cookie_secure=True)


def test_native_and_loopback_origins_are_allowed():
    origins = "https://a.b,capacitor://localhost,ionic://localhost,http://localhost:8001"
    check_production_config({**GOOD, "ALLOWED_ORIGINS": origins}, cookie_secure=True)


@pytest.mark.parametrize(
    "override",
    [
        {"AUTH_DEV_BYPASS": "true"},
        {"INTERNAL_API_TOKEN": ""},
        {"ALLOWED_ORIGINS": ""},
        {"ALLOWED_ORIGINS": "*"},
        {"ALLOWED_ORIGINS": "http://legacy.example.org"},
        {"ALLOWED_ORIGINS": "https://a.b,http://203.0.113.10:8080"},
        {"ALLOWED_ORIGINS": "http://localhost.evil.example"},
    ],
)
def test_bad_production_config_refuses_to_boot(override):
    with pytest.raises(RuntimeError):
        check_production_config({**GOOD, **override}, cookie_secure=True)


def test_insecure_cookie_refuses_to_boot():
    with pytest.raises(RuntimeError, match="cookie_secure"):
        check_production_config(GOOD, cookie_secure=False)
