import pytest
from pydantic import ValidationError

from config.settings import get_settings


def test_loads_and_converts_dotenv_values():
    settings = get_settings()

    assert settings.server_host == "127.0.0.1"
    assert settings.server_port == 8000
    assert settings.server_reload is True
    assert settings.mysql_database == "test_database"
    assert settings.mysql_password.get_secret_value() == ""
    assert settings.llm_model == ""


def test_environment_overrides_dotenv_and_masks_secrets(monkeypatch):
    monkeypatch.setenv("APP_SERVER_PORT", "8001")
    monkeypatch.setenv("APP_SERVER_RELOAD", "false")
    monkeypatch.setenv("APP_LLM_MODEL", "123")
    monkeypatch.setenv("APP_LLM_BASE_URL", "https://ai.example.com/v1")
    monkeypatch.setenv("APP_LLM_API_KEY", "test-api-key")
    monkeypatch.setenv("APP_MYSQL_PASSWORD", "test-password")

    settings = get_settings()

    assert settings.server_host == "127.0.0.1"
    assert settings.server_port == 8001
    assert settings.server_reload is False
    assert settings.llm_model == "123"
    assert settings.llm_base_url == "https://ai.example.com/v1"
    assert settings.llm_api_key.get_secret_value() == "test-api-key"
    assert settings.mysql_password.get_secret_value() == "test-password"
    for secret in ("test-api-key", "test-password"):
        assert secret not in repr(settings)
        assert secret not in settings.model_dump_json()


def test_masks_secrets_loaded_from_dotenv(config_dir):
    path = config_dir / ".env.local"
    path.write_text(path.read_text().replace("APP_LLM_API_KEY=", "APP_LLM_API_KEY=file-secret"))

    settings = get_settings()

    assert settings.llm_api_key.get_secret_value() == "file-secret"
    assert "file-secret" not in settings.model_dump_json()


@pytest.mark.parametrize("environment", ["test", "staging", "production"])
def test_selects_only_requested_environment(monkeypatch, config_dir, env_content, environment):
    (config_dir / f".env.{environment}").write_text(
        env_content.replace("APP_SERVER_PORT=8000", "APP_SERVER_PORT=9000")
    )
    (config_dir / ".env.local").write_text("APP_SERVER_PORT=invalid")
    monkeypatch.setenv("APP_ENV", environment)

    assert get_settings().server_port == 9000


def test_rejects_unknown_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "unknown")

    with pytest.raises(ValueError, match="unknown"):
        get_settings()


@pytest.mark.parametrize(
    ("field", "value"),
    [("SERVER_PORT", "0"), ("SERVER_PORT", "65536"), ("SERVER_PORT", "invalid"),
     ("SERVER_RELOAD", "invalid"), ("MYSQL_PORT", "0"), ("MYSQL_HOST", ""),
     ("LOGGING_LEVEL", "invalid")],
)
def test_rejects_invalid_configuration(monkeypatch, field, value):
    monkeypatch.setenv(f"APP_{field}", value)

    with pytest.raises(ValidationError) as error:
        get_settings()

    assert error.value.errors()[0]["loc"] == (field.lower(),)


def test_missing_required_values_fail_at_startup(config_dir):
    (config_dir / ".env.local").write_text("")

    with pytest.raises(ValidationError):
        get_settings()


def test_runs_with_environment_variables_without_dotenv(monkeypatch, config_dir, env_content):
    (config_dir / ".env.local").unlink()
    for line in env_content.splitlines():
        key, value = line.split("=", 1)
        monkeypatch.setenv(key, value)

    assert get_settings().server_port == 8000


def test_dotenv_path_is_independent_of_working_directory(monkeypatch, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)

    assert get_settings().server_port == 8000


def test_settings_are_cached(monkeypatch):
    original = get_settings()
    monkeypatch.setenv("APP_SERVER_PORT", "9000")

    assert get_settings() is original
    get_settings.cache_clear()
    assert get_settings().server_port == 9000


@pytest.mark.parametrize(
    ("value", "expected"),
    [("", ""), ("/", ""), ("/workbase-ai", "/workbase-ai"), ("/api/v1/", "/api/v1")],
)
def test_normalizes_base_path(monkeypatch, value, expected):
    monkeypatch.setenv("APP_SERVER_BASE_PATH", value)

    assert get_settings().server_base_path == expected


@pytest.mark.parametrize("value", ["api", "//api", "/api?debug=1", "/api/../other"])
def test_rejects_invalid_base_path(monkeypatch, value):
    monkeypatch.setenv("APP_SERVER_BASE_PATH", value)

    with pytest.raises(ValidationError):
        get_settings()
