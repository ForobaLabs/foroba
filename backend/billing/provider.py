"""Checkout provider seam. `fake` is the default: nothing reaches a real payment service."""

from __future__ import annotations

import json
from typing import Literal, Protocol, get_args

from config import settings

Plan = Literal["premium_monthly", "premium_yearly", "expert_monthly", "expert_yearly"]
PLANS: tuple[str, ...] = get_args(Plan)


class BillingProviderError(Exception):
    pass


class CheckoutProvider(Protocol):
    def create_checkout(self, *, user_id: int, email: str, plan: str) -> str: ...


class FakeProvider:
    def create_checkout(self, *, user_id: int, email: str, plan: str) -> str:
        return f"https://billing.invalid/checkout?plan={plan}"


class PaddleProvider:
    """Stub: real transaction creation is wired at go-live (needs vendor account, price ids).

    Resolves the price id server-side from settings.paddle_price_ids; makes no network call.
    """

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
