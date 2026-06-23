"""Application configuration loaded from environment variables.

All required settings are validated at import time via pydantic-settings.
The application refuses to start if any required variable is missing or invalid.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    ENVIRONMENT: Literal["development", "production", "test"] = "development"

    DATABASE_URL: str = Field(..., min_length=1)
    REDIS_URL: str = Field(..., min_length=1)

    RSA_PRIVATE_KEY: str = Field(..., min_length=1)
    RSA_PUBLIC_KEY: str = Field(..., min_length=1)

    GOOGLE_CLIENT_ID: str = Field(..., min_length=1)
    GOOGLE_CLIENT_SECRET: str = Field(..., min_length=1)
    GOOGLE_REDIRECT_URI: str = Field(default="http://localhost:8000/api/v1/auth/google/callback")

    TMDB_API_KEY: str = Field(..., min_length=1)
    OPENAI_API_KEY: str = Field(..., min_length=1)
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")

    FRONTEND_URL: str = Field(..., min_length=1)
    ALLOWED_ORIGINS: str = Field(..., min_length=1)

    ACCESS_TOKEN_TTL_MINUTES: int = Field(default=15, gt=0, le=60)
    REFRESH_TOKEN_TTL_DAYS: int = Field(default=7, gt=0, le=30)

    SESSION_SECRET: str = Field(..., min_length=16)

    JWT_ISSUER: str = Field(default="flick")
    JWT_AUDIENCE: str = Field(default="flick-clients")

    @field_validator("RSA_PRIVATE_KEY", "RSA_PUBLIC_KEY")
    @classmethod
    def _normalize_pem(cls, v: str) -> str:
        # Allow newline-escaped PEM strings from .env files.
        return v.replace("\\n", "\n")

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT == "test"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
