"""Basic load test for foroba key endpoints (TI-B item 7, foroba#156).

Goal: find where SQLite (single-writer) starts to degrade under concurrent
household-scale usage, not to simulate internet-scale traffic.

Run:
    .venv/bin/locust -f loadtest/locustfile.py --host http://localhost:8002 \
        --headless -u <users> -r <spawn-rate> -t <duration> \
        --csv loadtest/results/run
"""
from __future__ import annotations

import random
import uuid

from locust import HttpUser, between, task


class AnonymousUser(HttpUser):
    """Simulates unauthenticated traffic: health polling + login attempts."""

    weight = 1
    wait_time = between(1, 3)

    @task(5)
    def health(self) -> None:
        self.client.get("/health", name="/health")

    @task(1)
    def login_demo(self) -> None:
        self.client.post(
            "/auth/login",
            json={"email": "demo@foroba.app", "password": "Demo!2026"},
            name="/auth/login",
        )


class AuthenticatedUser(HttpUser):
    """Simulates a logged-in user hitting read endpoints (dominant traffic pattern)."""

    weight = 4
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.client.post(
            "/auth/login",
            json={"email": "demo@foroba.app", "password": "Demo!2026"},
            name="/auth/login",
        )

    @task(3)
    def me(self) -> None:
        self.client.get("/auth/me", name="/auth/me")

    @task(2)
    def markets_snapshot(self) -> None:
        symbol = random.choice(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        self.client.get(
            "/markets/snapshot",
            params={"symbol": symbol, "asset_class": "crypto"},
            name="/markets/snapshot",
        )

    @task(2)
    def markets_overview(self) -> None:
        self.client.get("/markets/overview", name="/markets/overview")

    @task(1)
    def household(self) -> None:
        self.client.get("/auth/household", name="/auth/household")


class RegisterUser(HttpUser):
    """Simulates new-user signup traffic (write-heavy, exercises SQLite writes)."""

    weight = 1
    wait_time = between(2, 5)

    @task
    def register(self) -> None:
        email = f"loadtest-{uuid.uuid4().hex[:12]}@example.com"
        self.client.post(
            "/auth/register",
            json={"email": email, "name": "Load Test", "password": "password123"},
            name="/auth/register",
        )
