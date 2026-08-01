"""Tests for fx_scheduler.py — TI-D item 3 Plan 3, foroba#164."""

from __future__ import annotations

from unittest.mock import patch

import fx_scheduler


def test_start_fx_scheduler_registers_daily_job():
    with patch("fx_scheduler.BackgroundScheduler") as MockScheduler:
        instance = MockScheduler.return_value
        result = fx_scheduler.start_fx_scheduler()

        assert result is instance
        instance.add_job.assert_called_once()
        _, kwargs = instance.add_job.call_args
        assert kwargs["id"] == "fx_rate_refresh"
        instance.start.assert_called_once()
