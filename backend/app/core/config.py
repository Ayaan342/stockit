from decimal import Decimal

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded exclusively from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = Field(default="development", validation_alias="APP_ENV")
    jwt_secret: str = Field(default="", validation_alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60 * 24, gt=0)
    initial_virtual_cash: Decimal = Field(default=Decimal("100000.00"), ge=0)
    market_data_api_key: str = Field(default="", validation_alias="MARKET_DATA_API_KEY")
    market_data_base_url: str = "https://api.twelvedata.com"
    market_data_timeout_seconds: float = Field(default=4.0, gt=0, le=15, validation_alias="MARKET_DATA_TIMEOUT_SECONDS")
    market_cache_seconds: int = Field(default=60, ge=0, le=3600)
    market_stale_cache_seconds: int = Field(default=900, ge=60, le=86400, validation_alias="MARKET_STALE_CACHE_SECONDS")
    market_primary_cooldown_seconds: int = Field(default=30, ge=0, le=600, validation_alias="MARKET_PRIMARY_COOLDOWN_SECONDS")
    market_history_cache_seconds: int = Field(default=3600, ge=60, le=86400, validation_alias="MARKET_HISTORY_CACHE_SECONDS")

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.app_env == "production" and not self.jwt_secret:
            raise ValueError("JWT_SECRET must be configured when APP_ENV is production")
        return self


settings = Settings()
