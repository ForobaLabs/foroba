import logging
import smtplib
from typing import ClassVar

import pytest

import email_service
from config import settings


class FakeSMTP:
    """Stands in for smtplib.SMTP — records calls instead of opening a real
    socket. `instances` is a class-level list so tests can assert on what
    would have been sent."""

    instances: ClassVar[list["FakeSMTP"]] = []

    def __init__(self, host, port, timeout=10):
        self.host = host
        self.port = port
        self.started_tls = False
        self.logged_in = None
        self.sent = None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, user, password):
        self.logged_in = (user, password)

    def sendmail(self, from_addr, to_addrs, msg):
        self.sent = (from_addr, to_addrs, msg)


@pytest.fixture(autouse=True)
def _reset_fake_smtp():
    FakeSMTP.instances.clear()
    yield
    FakeSMTP.instances.clear()
    settings.smtp_enabled = False


def test_send_email_logs_when_disabled(caplog):
    settings.smtp_enabled = False
    with caplog.at_level(logging.INFO):
        email_service.send_email("user@test.local", "Subject", "Body")
    assert "would send email to user@test.local" in caplog.text
    assert FakeSMTP.instances == []


def test_send_email_sends_via_smtp_when_enabled(monkeypatch):
    settings.smtp_enabled = True
    settings.smtp_host = "smtp.test.local"
    settings.smtp_port = 587
    settings.smtp_user = "bot@test.local"
    settings.smtp_password = "secret"
    settings.smtp_from = "noreply@test.local"
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    email_service.send_email("user@test.local", "Subject", "Body text")

    assert len(FakeSMTP.instances) == 1
    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.test.local"
    assert smtp.port == 587
    assert smtp.started_tls is True
    assert smtp.logged_in == ("bot@test.local", "secret")
    from_addr, to_addrs, msg = smtp.sent
    assert from_addr == "noreply@test.local"
    assert to_addrs == ["user@test.local"]
    assert "Subject: Subject" in msg
    assert "Body text" in msg


def test_send_email_skips_login_when_no_smtp_user(monkeypatch):
    settings.smtp_enabled = True
    settings.smtp_host = "smtp.test.local"
    settings.smtp_port = 587
    settings.smtp_user = ""
    settings.smtp_password = ""
    settings.smtp_from = "noreply@test.local"
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    email_service.send_email("user@test.local", "Subject", "Body")

    assert FakeSMTP.instances[0].logged_in is None


def test_send_email_does_not_raise_on_smtp_failure(monkeypatch, caplog):
    """A transient SMTP failure must not propagate. monthly_report_service.py's
    _run_generation() calls send_email() AFTER already persisting the report
    row as status='success' — if send_email raised here, that function's
    outer except-block would incorrectly flip an already-successful report
    to 'failed' just because the notification email didn't go out."""
    settings.smtp_enabled = True
    settings.smtp_host = "smtp.test.local"
    settings.smtp_from = "noreply@test.local"

    class BrokenSMTP(FakeSMTP):
        def sendmail(self, from_addr, to_addrs, msg):
            raise smtplib.SMTPException("connection refused")

    monkeypatch.setattr(smtplib, "SMTP", BrokenSMTP)

    with caplog.at_level(logging.ERROR):
        email_service.send_email("user@test.local", "Subject", "Body")  # must not raise

    assert "Failed to send email" in caplog.text
