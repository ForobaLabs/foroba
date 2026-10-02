"""Normalise a Paddle webhook payload into a provider-neutral subscription event."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class SubscriptionEvent:
    event_id: str
    event_type: str
    occurred_at: datetime
    subscription_id: str
    customer_id: str | None
    user_id: int | None
    status: str
    period_end: datetime | None
    cancel_at_period_end: bool


def _dt(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_paddle_event(payload: dict) -> SubscriptionEvent | None:
    """Return None for anything that is not a well-formed subscription.* event."""
    if not isinstance(payload, dict):
        return None
    event_type = payload.get("event_type")
    event_id = payload.get("event_id")
    data = payload.get("data")
    if not (isinstance(event_type, str) and event_type.startswith("subscription.")):
        return None
    if not (isinstance(event_id, str) and event_id and isinstance(data, dict)):
        return None
    occurred = _dt(payload.get("occurred_at"))
    sub_id = data.get("id")
    status = data.get("status")
    if occurred is None or not isinstance(sub_id, str) or not isinstance(status, str):
        return None
    custom = data.get("custom_data") if isinstance(data.get("custom_data"), dict) else {}
    try:
        user_id = int(custom.get("user_id"))
    except (TypeError, ValueError):
        user_id = None
    period = (
        data.get("current_billing_period")
        if isinstance(data.get("current_billing_period"), dict)
        else {}
    )
    change = data.get("scheduled_change") if isinstance(data.get("scheduled_change"), dict) else {}
    return SubscriptionEvent(
        event_id=event_id,
        event_type=event_type,
        occurred_at=occurred,
        subscription_id=sub_id,
        customer_id=data.get("customer_id") if isinstance(data.get("customer_id"), str) else None,
        user_id=user_id,
        status=status,
        period_end=_dt(period.get("ends_at")),
        cancel_at_period_end=change.get("action") == "cancel",
    )
