"""Environment-backed FastCal configuration."""

from __future__ import annotations

import re

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    FASTCAL_ENV: str = "development"
    FASTCAL_HOST: str = "0.0.0.0"
    FASTCAL_PORT: int = 5021
    FASTCAL_PUBLIC_URL: str = "http://localhost:5021"
    FASTCAL_SECRET: str = "development-only-change-me"
    FASTCAL_ENCRYPTION_KEY: str = ""
    FASTCAL_DEV_LOGIN: bool = True
    DB_URL: str = "postgresql://postgres:postgres@localhost:5432/fastcal"
    DB_SCHEMA: str = "fast_cal"

    FASTOFFICE_URL: str = "http://localhost:5020"
    FASTOFFICE_SSO_SECRET: str = ""
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""
    GOOGLE_ALLOWED_DOMAINS: str = ""
    GOOGLE_ALLOWED_EMAILS: str = ""

    POSTMARK_API_TOKEN: str = ""
    FROM_EMAIL: str = "info@fastsme.com"
    FASTMEET_URL: str = "https://meet.fastsme.com"
    FASTMEET_API_TOKEN: str = ""

    @field_validator("DB_SCHEMA")
    @classmethod
    def safe_schema(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value):
            raise ValueError("DB_SCHEMA must be a safe PostgreSQL identifier")
        return value

    @property
    def production(self) -> bool:
        return self.FASTCAL_ENV.lower() == "production"

    @property
    def google_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)


settings = Settings()
