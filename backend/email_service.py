"""Email delivery for monthly report notifications (foroba#159, TI-D item 2).

Real SMTP wiring is explicitly deferred — see foroba#163. Until
settings.smtp_enabled is flipped on, this only logs what would have been sent,
so the rest of the generation flow can be built/tested against a stable
interface today.
"""
from __future__ import annotations

import logging

from config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> None:
    if not settings.smtp_enabled:
        logger.info("SMTP disabled — would send email to %s: %s", to, subject)
        return
    raise NotImplementedError("Real SMTP not wired yet — see foroba#163")
