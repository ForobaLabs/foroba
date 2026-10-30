"""ai-gateway settings. The gateway is the only holder of provider credentials."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", populate_by_name=True
    )

    ai_gateway_token: str = Field(validation_alias="AI_GATEWAY_TOKEN")
    foroba_jwks_url: str = Field(validation_alias="FOROBA_JWKS_URL")

    db_path: str = Field("data/ai_gateway.db", validation_alias="AI_GATEWAY_DB_PATH")
    db_encryption_key: str = Field(validation_alias="AI_GATEWAY_DB_KEY")
    field_key: str = Field(validation_alias="AI_GATEWAY_FIELD_KEY")

    ai_cloud_enabled: bool = Field(False, validation_alias="AI_CLOUD_ENABLED")
    cf_account_id: str = Field("", validation_alias="CF_ACCOUNT_ID")
    cf_api_token: str = Field("", validation_alias="CF_API_TOKEN")

    allowance_free_neurons: int = Field(
        20000, validation_alias="AI_ALLOWANCE_FREE_NEURONS"
    )
    allowance_premium_neurons: int = Field(
        300000, validation_alias="AI_ALLOWANCE_PREMIUM_NEURONS"
    )
    cf_monthly_neurons: int = Field(900000, validation_alias="CF_AI_MONTHLY_NEURONS")
    cf_daily_soft_neurons: int = Field(
        60000, validation_alias="CF_AI_DAILY_SOFT_NEURONS"
    )

    test_allowlist: Annotated[set[int], NoDecode] = Field(
        default_factory=set, validation_alias="AI_TEST_ALLOWLIST"
    )
    rate_limit_per_min: int = Field(10, validation_alias="AI_RATE_LIMIT_PER_MIN")

    model_chat: str = Field(
        "@cf/meta/llama-4-scout-17b-16e-instruct", validation_alias="AI_MODEL_CHAT"
    )
    model_tools: str = Field(
        "@cf/meta/llama-4-scout-17b-16e-instruct", validation_alias="AI_MODEL_TOOLS"
    )
    model_extract: str = Field(
        "@cf/meta/llama-4-scout-17b-16e-instruct", validation_alias="AI_MODEL_EXTRACT"
    )
    model_long: str = Field(
        "@cf/meta/llama-4-scout-17b-16e-instruct", validation_alias="AI_MODEL_LONG"
    )

    fallback_provider: Literal["none", "gemini"] = Field(
        "none", validation_alias="AI_FALLBACK_PROVIDER"
    )
    gemini_api_key: str = Field("", validation_alias="GEMINI_API_KEY")
    model_fallback: str = Field("gemini-3.5-flash-lite", validation_alias="AI_MODEL_FALLBACK")

    @field_validator("test_allowlist", mode="before")
    @classmethod
    def _parse_allowlist(cls, v):
        if isinstance(v, str):
            return {int(x) for x in v.split(",") if x.strip()}
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
