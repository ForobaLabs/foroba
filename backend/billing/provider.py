"""Checkout provider seam. `fake` is the default: nothing reaches a real payment service."""

from __future__ import annotations

from typing import Protocol


class BillingProviderError(Exception):
    pass


class CheckoutProvider(Protocol):
    def create_checkout(self, *, user_id: int, email: str, plan: str) -> str: ...


class FakeProvider:
    def create_checkout(self, *, user_id: int, email: str, plan: str) -> str:
        return f"https://billing.invalid/checkout?plan={plan}"


class PaddleProvider:
    """Stub: real transaction creation is wired at go-live (needs vendor account, price ids)."""

    def create_checkout(self, *, user_id: int, email: str, plan: str) -> str:
        raise BillingProviderError("Paddle checkout is not configured")


def get_provider(name: str) -> CheckoutProvider:
    return PaddleProvider() if name == "paddle" else FakeProvider()
