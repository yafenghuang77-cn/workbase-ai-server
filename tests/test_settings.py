import pytest
import yaml
from pydantic import ValidationError

from config.settings import Settings, get_settings


def test_defaults_to_local_with_reload():
    settings = get_settings()

    assert settings.server.host == "127.0.0.1"
    assert settings.server.port == 8000
    assert settings.server.reload is True
    assert settings.logging.level == "DEBUG"


def test_nested_environment_overrides_preserve_other_yaml_fields(monkeypatch):
    monkeypatch.setenv("APP_SERVER__PORT", "8001")
    monkeypatch.setenv("APP_LOGGING__LEVEL", "INFO")

    settings = Settings()

    assert settings.server.port == 8001
    assert settings.logging.level == "INFO"
    assert settings.server.host == "127.0.0.1"
    assert settings.server.reload is True


@pytest.mark.parametrize("value", ["0", "65536", "invalid"])
def test_rejects_invalid_port(monkeypatch, value):
    monkeypatch.setenv("APP_SERVER__PORT", value)

    with pytest.raises(ValidationError) as error:
        Settings()

    assert error.value.errors()[0]["loc"] == ("server", "port")


def test_loads_mysql_configuration():
    mysql = get_settings().mysql

    assert mysql.host == "127.0.0.1"
    assert mysql.port == 3306
    assert mysql.database == "test_database"
    assert mysql.username == "test_user"
    assert mysql.password.get_secret_value() == ""
    assert mysql.charset == "utf8mb4"


def test_mysql_environment_overrides_and_masks_password(monkeypatch):
    password = "test-password-not-a-real-secret"
    overrides = {
        "HOST": "mysql.internal",
        "PORT": "3307",
        "DATABASE": "custom_database",
        "USERNAME": "custom_user",
        "PASSWORD": password,
    }
    for field, value in overrides.items():
        monkeypatch.setenv(f"APP_MYSQL__{field}", value)

    settings = Settings()

    assert settings.mysql.host == "mysql.internal"
    assert settings.mysql.port == 3307
    assert settings.mysql.database == "custom_database"
    assert settings.mysql.username == "custom_user"
    assert settings.mysql.password.get_secret_value() == password
    assert settings.mysql.charset == "utf8mb4"
    assert password not in repr(settings)
    assert password not in settings.model_dump_json()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("PORT", "0"),
        ("PORT", "65536"),
        ("PORT", "invalid"),
        ("HOST", ""),
        ("DATABASE", ""),
        ("USERNAME", ""),
        ("CHARSET", ""),
    ],
)
def test_rejects_invalid_mysql_configuration(monkeypatch, field, value):
    monkeypatch.setenv(f"APP_MYSQL__{field}", value)

    with pytest.raises(ValidationError) as error:
        Settings()

    assert error.value.errors()[0]["loc"] == ("mysql", field.lower())


def test_rejects_unknown_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "unknown")

    with pytest.raises(ValueError, match="unknown"):
        Settings()


@pytest.mark.parametrize("environment", ["test", "staging", "production"])
def test_selects_only_requested_environment_file(
    monkeypatch, config_dir, config_data, environment
):
    config_data["server"].update(port=9000, reload=False)
    (config_dir / f"{environment}.yaml").write_text(
        yaml.safe_dump(config_data), encoding="utf-8"
    )
    (config_dir / "local.yaml").write_text("invalid: local", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", environment)

    settings = Settings()

    assert settings.server.port == 9000
    assert settings.server.reload is False


def test_rejects_missing_file(config_dir):
    (config_dir / "local.yaml").unlink()

    with pytest.raises(FileNotFoundError, match="local.yaml"):
        Settings()


def test_rejects_empty_file(config_dir):
    (config_dir / "local.yaml").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="empty"):
        Settings()


def test_rejects_incomplete_file(config_dir):
    (config_dir / "local.yaml").write_text("server:\n  port: 8000\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        Settings()


def test_yaml_path_does_not_depend_on_working_directory(monkeypatch, tmp_path):
    working_directory = tmp_path / "other_directory"
    working_directory.mkdir()
    monkeypatch.chdir(working_directory)

    assert Settings().server.port == 8000


def test_loads_new_yaml_fields_without_model_changes(config_dir, config_data):
    config_data["redis"] = {
        "host": "localhost",
        "tls": {"enabled": False},
        "nodes": [{"host": "node-a", "port": 6379}],
    }
    config_data["server"]["workers"] = 2
    config_data["mysql"]["pool"] = {"size": 5}
    config_data["labels"] = ["local", "test"]
    config_data["optional"] = None
    config_data["model_dump"] = "accessible by key"
    (config_dir / "local.yaml").write_text(yaml.safe_dump(config_data), encoding="utf-8")

    settings = Settings()

    assert settings.redis.host == "localhost"
    assert settings.redis.tls.enabled is False
    assert settings.redis.nodes[0].port == 6379
    assert settings.server.workers == 2
    assert settings.mysql.pool.size == 5
    assert settings["redis"]["tls"]["enabled"] is False
    assert settings.labels == ["local", "test"]
    assert settings.optional is None
    assert settings["model_dump"] == "accessible by key"
    assert settings.model_dump(mode="json", exclude_unset=True) == config_data


def test_environment_overrides_new_sections(monkeypatch):
    monkeypatch.setenv("APP_REDIS__HOST", "redis.internal")
    monkeypatch.setenv("APP_REDIS__PORT", "6380")
    monkeypatch.setenv("APP_REDIS__TLS__ENABLED", "true")
    monkeypatch.setenv("APP_REDIS__NODES", '[{"host":"node-a"}]')

    settings = Settings()

    assert settings.redis.host == "redis.internal"
    assert settings.redis.port == 6380
    assert settings.redis.tls.enabled is True
    assert settings.redis.nodes[0].host == "node-a"


def test_json_and_nested_environment_overrides_merge_yaml(monkeypatch, config_dir, config_data):
    config_data["redis"] = {"host": "localhost", "port": 6379}
    (config_dir / "local.yaml").write_text(yaml.safe_dump(config_data), encoding="utf-8")
    monkeypatch.setenv("APP_REDIS", '{"port":6380,"tls":{"enabled":false}}')
    monkeypatch.setenv("APP_REDIS__TLS__ENABLED", "true")
    monkeypatch.setenv("APP_MYSQL__USERNAME", "123")

    settings = Settings()

    assert settings.redis.host == "localhost"
    assert settings.redis.port == 6380
    assert settings.redis.tls.enabled is True
    assert settings.mysql.username == "123"


@pytest.mark.parametrize("content", ["[]", "false", "123", "plain text"])
def test_rejects_non_mapping_yaml(config_dir, content):
    (config_dir / "local.yaml").write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="mapping"):
        Settings()


@pytest.mark.parametrize(
    ("value", "expected"),
    [("", ""), ("/", ""), ("/workbase-ai", "/workbase-ai"), ("/api/v1/", "/api/v1")],
)
def test_normalizes_base_path(monkeypatch, value, expected):
    monkeypatch.setenv("APP_SERVER__BASE_PATH", value)

    assert Settings().server.base_path == expected


@pytest.mark.parametrize("value", ["api", "//api", "/api?debug=1", "/api/../other"])
def test_rejects_invalid_base_path(monkeypatch, value):
    monkeypatch.setenv("APP_SERVER__BASE_PATH", value)

    with pytest.raises(ValidationError) as error:
        Settings()

    assert error.value.errors()[0]["loc"] == ("server", "base_path")
