import pytest
from pydantic import ValidationError

from auth.models import EmailOtpVerifyRequest, Login2FARequest, RecoveryCodeLoginRequest


def test_login_2fa_request_accepts_method_field():
    req = Login2FARequest(email="a@example.com", code="123456", method="totp")
    assert req.method == "totp"


def test_login_2fa_request_defaults_method_to_totp():
    req = Login2FARequest(email="a@example.com", code="123456")
    assert req.method == "totp"


def test_login_2fa_request_rejects_unknown_method():
    with pytest.raises(ValidationError):
        Login2FARequest(email="a@example.com", code="123456", method="sms")


def test_email_otp_verify_request():
    req = EmailOtpVerifyRequest(email="a@example.com", code="654321")
    assert req.code == "654321"


def test_recovery_code_login_request():
    req = RecoveryCodeLoginRequest(email="a@example.com", recovery_code="ABCD123456")
    assert req.recovery_code == "ABCD123456"
