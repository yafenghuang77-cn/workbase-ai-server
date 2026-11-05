import json
import os
import re
from collections.abc import Callable
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class ConfigSection(BaseModel):
    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def wrap_extra_sections(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        return {
            key: value if key in cls.model_fields else _wrap_config(value)
            for key, value in data.items()
        }

    def __getitem__(self, key: str) -> Any:
        if key in type(self).model_fields:
            return getattr(self, key)
        return self.__pydantic_extra__[key]


def _wrap_config(value: Any) -> Any:
    if isinstance(value, dict):
        return ConfigSection.model_validate(value)
    if isinstance(value, list):
        return [_wrap_config(item) for item in value]
    return value


def _environment_overrides(config: dict[str, Any]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    variables = sorted(os.environ, key=lambda name: name.count("__"))
    for name in variables:
        if not name.upper().startswith("APP_") or name.upper() == "APP_ENV":
            continue
        parts = name[4:].split("__")
        if any(not part for part in parts):
            raise ValueError(f"Invalid configuration environment variable: {name}")
        target = overrides
        template = config
        for index, part in enumerate(parts):
            known = template if isinstance(template, dict) else {}
            key = next(
                (key for key in known if key.lower() == part.lower()), part.lower()
            )
            template = known.get(key)
            if index == len(parts) - 1:
                value = os.environ[name]
                if not isinstance(template, str):
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        pass
                target[key] = value
            else:
                target = target.setdefault(key, {})
                if not isinstance(target, dict):
                    raise ValueError(f"Conflicting configuration environment variable: {name}")
    return overrides


class ServerSettings(ConfigSection):

    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    reload: bool
    base_path: str = ""

    @field_validator("base_path")
    @classmethod
    def validate_base_path(cls, value: str) -> str:
        if value in ("", "/"):
            return ""
        value = value.rstrip("/")
        if not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)+", value):
            raise ValueError(
                "base_path must start with / and contain only path segments "
                "of letters, digits, _ or -"
            )
        return value


class LoggingSettings(ConfigSection):

    level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "TRACE"]


class MySQLSettings(ConfigSection):

    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    database: str = Field(min_length=1)
    username: str = Field(min_length=1)
    password: SecretStr
    charset: str = Field(min_length=1)


class Settings(BaseSettings, ConfigSection):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_nested_delimiter="__",
        extra="allow",
    )

    server: ServerSettings
    logging: LoggingSettings
    mysql: MySQLSettings

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource | Callable[[], dict[str, Any]], ...]:
        environment = Environment(os.environ.get("APP_ENV", "local"))
        config_file = Path(__file__).resolve().parent / f"{environment.value}.yaml"
        if not config_file.is_file():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")

        with config_file.open(encoding="utf-8") as file:
            config = yaml.safe_load(file)
        if config is None or config == {}:
            raise ValueError(f"Configuration file is empty: {config_file}")
        if not isinstance(config, dict):
            raise ValueError(f"Configuration file must contain a mapping: {config_file}")

        return init_settings, lambda: _environment_overrides(config), lambda: config


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
