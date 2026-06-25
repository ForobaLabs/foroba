"""Entitlements endpoint and the require_feature dependency factory."""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from config import settings
from auth.dependencies import get_current_user
from auth.entitlements import REGISTRY, evaluate

router = APIRouter(prefix="/auth", tags=["entitlements"])


@router.get("/entitlements")
def list_entitlements(user: dict = Depends(get_current_user)) -> dict:
    features = {
        key: {
            "audience": meta["audience"],
            "tier": meta["tier"],
            **evaluate(key, user, gating_enabled=settings.premium_gating_enabled).__dict__,
        }
        for key, meta in REGISTRY.items()
    }
    return {
        "user": {"tier": user["tier"], "audience": user["audience"]},
        "gating_enabled": settings.premium_gating_enabled,
        "features": features,
    }


def require_feature(key: str) -> Callable[..., dict]:
    """Dependency factory: 403 if not visible (audience), 402 if locked (tier)."""
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        access = evaluate(key, user, gating_enabled=settings.premium_gating_enabled)
        if not access.visible:
            raise HTTPException(403, {"error": {"code": "audience_required", "feature": key}})
        if not access.unlocked:
            raise HTTPException(402, {"error": {"code": "premium_required", "feature": key}})
        return user
    return _dep
