import pyotp

from twofa.totp import generate_secret, provisioning_uri, qr_data_url, verify_code


def test_generate_secret_is_base32_and_unique():
    a, b = generate_secret(), generate_secret()
    assert a != b
    pyotp.TOTP(a).now()  # does not raise -> valid base32


def test_provisioning_uri_contains_issuer_and_account():
    uri = provisioning_uri("SECRET234567", account="demo@foroba.app")
    assert uri.startswith("otpauth://totp/")
    assert "Foroba" in uri
    assert "demo" in uri and "foroba.app" in uri


def test_verify_code_accepts_current_and_rejects_wrong():
    secret = generate_secret()
    code = pyotp.TOTP(secret).now()
    assert verify_code(secret, code) is True
    assert verify_code(secret, "000000") is False


def test_qr_data_url_is_png_base64():
    url = qr_data_url("otpauth://totp/Foroba:demo?secret=ABC&issuer=Foroba")
    assert url.startswith("data:image/png;base64,")


def test_verify_code_rejects_replay_of_an_accepted_code():
    secret = generate_secret()
    code = pyotp.TOTP(secret).now()
    assert verify_code(secret, code) is True
    assert verify_code(secret, code) is False


def test_verify_code_rejects_an_older_step_after_a_newer_one():
    import time

    secret = generate_secret()
    totp = pyotp.TOTP(secret)
    now = time.time()
    assert verify_code(secret, totp.at(now)) is True
    assert verify_code(secret, totp.at(now - 30)) is False


def test_replay_guard_is_per_secret():
    a, b = generate_secret(), generate_secret()
    assert verify_code(a, pyotp.TOTP(a).now()) is True
    assert verify_code(b, pyotp.TOTP(b).now()) is True


def test_enrolment_confirmation_does_not_consume_the_step():
    secret = generate_secret()
    code = pyotp.TOTP(secret).now()
    assert verify_code(secret, code, consume=False) is True
    assert verify_code(secret, code) is True
    assert verify_code(secret, code) is False
