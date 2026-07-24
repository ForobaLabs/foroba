"""Pydantic request/response models for auth endpoints."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    email_confirm: EmailStr
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    password_confirm: str
    birth_year: int | None = Field(default=None, ge=1900, le=2100)
    country: str | None = Field(default=None, min_length=2, max_length=2)

    @model_validator(mode="after")
    def _check_confirmations(self) -> RegisterRequest:
        if self.email.lower() != self.email_confirm.lower():
            raise ValueError("Email and confirmation do not match")
        if self.password != self.password_confirm:
            raise ValueError("Password and confirmation do not match")
        return self


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
    birth_year: int | None = None
    country: str | None = None
    onboarding_completed_at: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: str | None = None


class HouseholdJoinRequest(BaseModel):
    email: EmailStr


class ShareToggleRequest(BaseModel):
    resource_type: str = Field(min_length=1, max_length=40)
    shared: bool


class DisplayCurrencyRequest(BaseModel):
    display_currency: str = Field(min_length=3, max_length=3)


class ShowDebtsRequest(BaseModel):
    show_debts: bool


class NameUpdateRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=0, max_length=80)
