"""Pydantic request/response models for auth endpoints."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    name: str
    tier: str
    audience: str
    audience_locked: bool
    is_admin: bool
    totp_enabled: bool
    display_currency: str
    show_debts: bool


class HouseholdJoinRequest(BaseModel):
    email: EmailStr


class ShareToggleRequest(BaseModel):
    resource_type: str = Field(min_length=1, max_length=40)
    shared: bool


class DisplayCurrencyRequest(BaseModel):
    display_currency: str = Field(min_length=3, max_length=3)


class ShowDebtsRequest(BaseModel):
    show_debts: bool
