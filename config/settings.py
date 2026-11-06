import os
import re
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_DIR = Path(__file__).resolve().parent.parent


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file_encoding="utf-8")

    server_host: str = Field(min_length=1)
    server_port: int = Field(ge=1, le=65535)
    server_reload: bool
    server_base_path: str = ""
    logging_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "TRACE"]

    mysql_host: str = Field(min_length=1)
    mysql_port: int = Field(ge=1, le=65535)
    mysql_database: str = Field(min_length=1)
    mysql_username: str = Field(min_length=1)
    mysql_password: SecretStr
    mysql_charset: str = Field(min_length=1)

    llm_model: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: str = ""

    @field_validator("server_base_path")
    @classmethod
    def validate_base_path(cls, value: str) -> str:
        if value in ("", "/"):
            return ""
        value = value.rstrip("/")
        if not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)+", value):
            raise ValueError("server_base_path must be a valid path starting with /")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    environment = Environment(os.environ.get("APP_ENV", "local"))
    return Settings(_env_file=CONFIG_DIR / f".env.{environment.value}")
