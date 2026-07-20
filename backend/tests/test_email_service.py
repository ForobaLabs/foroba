import logging

import pytest

import email_service
from config import settings


def test_send_email_logs_when_disabled(caplog):
    settings.smtp_enabled = False
    with caplog.at_level(logging.INFO):
        email_service.send_email("user@test.local", "Subject", "Body")
    assert "would send email to user@test.local" in caplog.text


def test_send_email_raises_when_enabled():
    settings.smtp_enabled = True
    try:
        with pytest.raises(NotImplementedError):
            email_service.send_email("user@test.local", "Subject", "Body")
    finally:
        settings.smtp_enabled = False
