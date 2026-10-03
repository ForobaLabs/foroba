"""Checkout provider seam. `fake` is the default: nothing reaches a real payment service."""

from __future__ import annotations

import json
from typing import Literal, Protocol, get_args

import httpx

from config import settings

Plan = Literal["premium_monthly", "premium_yearly", "expert_monthly", "expert_yearly"]
PLANS: tuple[str, ...] = get_args(Plan)


class BillingProviderError(Exception):
    pass


class CheckoutProvider(Protocol):
    def create_checkout(self, *, user_id: int, email: str, plan: str) -> str: ...

    def cancel_subscription(self, subscription_id: str) -> None: ...


class FakeProvider:
    def create_checkout(self, *, user_id: int, email: str, plan: str) -> str:
        return f"https://billing.invalid/checkout?plan={plan}"

    def cancel_subscription(self, subscription_id: str) -> None:
        return None


class PaddleProvider:
    """Stub: real transaction creation is wired at go-live (needs vendor account, price ids).

    Resolves the price id server-side from settings.paddle_price_ids; makes no network call.
    """

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport

    def cancel_subscription(self, subscription_id: str) -> None:
        """Cancel immediately: called before GDPR erasure so a deleted user is never billed."""
        if not settings.paddle_api_key:
            raise BillingProviderError("paddle_api_key is not configured")
        url = f"{settings.paddle_api_base.rstrip('/')}/subscriptions/{subscription_id}/cancel"
        try:
            with httpx.Client(timeout=15.0, transport=self._transport) as client:
                resp = client.post(
                    url,
                    json={"effective_from": "immediately"},
                    headers={"Authorization": f"Bearer {settings.paddle_api_key}"},
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise BillingProviderError(f"Paddle cancel failed for {subscription_id}") from exc

    def create_checkout(self, *, user_id: int, email: str, plan: str) -> str:
        try:
            prices = json.loads(settings.paddle_price_ids or "{}")
        except ValueError:
            raise BillingProviderError("paddle_price_ids is not valid JSON") from None
        if not isinstance(prices, dict) or not prices.get(plan):
            raise BillingProviderError(f"no price configured for {plan}")
        raise BillingProviderError("Paddle checkout is not implemented yet")


def get_provider(name: str) -> CheckoutProvider:
    return PaddleProvider() if name == "paddle" else FakeProvider()
