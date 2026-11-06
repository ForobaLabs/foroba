import pytest

from twofa import totp


@pytest.fixture(autouse=True)
def _reset_totp_replay_guard():
    """Tests share fixed TOTP secrets; start each one with an empty replay guard."""
    totp._last_step.clear()
    yield
    totp._last_step.clear()
