"""Email delivery for monthly report notifications (foroba#159, TI-D item 2).

Real SMTP wiring (foroba#163). Never raises — a transient SMTP failure must
not flip an otherwise-successful report to 'failed'. monthly_report_service.py's
_run_generation() calls send_email() AFTER the report row has already been
persisted as status='success'; that function's outer except-block treats any
exception as "generation failed" and would incorrectly overwrite a successful
report just because the notification email didn't go out. All SMTP errors are
therefore caught and logged here, not propagated.
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> None:
    if not settings.smtp_enabled:
        logger.info("SMTP disabled — would send email to %s: %s", to, subject)
        return
    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = to
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.sendmail(settings.smtp_from, [to], message.as_string())
    except (smtplib.SMTPException, OSError):
        logger.exception("Failed to send email to %s", to)
