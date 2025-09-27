from __future__ import annotations

import pathlib
from functools import lru_cache
from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = "Lost&Found Vision"
    debug: bool = False

    database_url: AnyUrl | str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/lostfound",
        validation_alias="DATABASE_URL",
    )

    jwt_private_key_path: pathlib.Path | None = Field(default=None, validation_alias="JWT_PRIVATE_KEY_PATH")
    jwt_public_key_path: pathlib.Path | None = Field(default=None, validation_alias="JWT_PUBLIC_KEY_PATH")
    jwt_issuer: str = Field(default="lostfound", validation_alias="JWT_ISSUER")
    jwt_audience: str = Field(default="lostfound-clients", validation_alias="JWT_AUDIENCE")
    access_token_ttl_seconds: int = Field(default=3600, validation_alias="ACCESS_TOKEN_TTL_SECONDS")

    question_bank_seed_path: pathlib.Path = Field(
        default=pathlib.Path("infra/seed/questions.json"),
        validation_alias="QUESTION_BANK_SEED_PATH",
    )

    default_match_limit: int = Field(default=5, ge=1, le=20)
    max_match_limit: int = Field(default=20, ge=1)

    rate_limit_per_minute: int = Field(default=60, ge=1)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
