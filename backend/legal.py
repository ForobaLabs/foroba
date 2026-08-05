"""Versioned legal document identifiers (foroba#219).

These version strings MUST be kept in sync by hand with the `lastUpdated` fields
of `DEFAULT_TERMS`/`DEFAULT_PRIVACY` in foroba-ui's `src/pages/LegalPage.tsx` —
bump both together whenever the Terms of Service or Privacy Policy text changes.
"""
from __future__ import annotations

TOS_VERSION = "2026-07-31"
PRIVACY_VERSION = "2026-07-31"
