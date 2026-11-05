import os

import pytest
import yaml
from fastapi.testclient import TestClient

import config.settings as settings_module
from config.settings import get_settings


@pytest.fixture
def config_data():
    return {
        "server": {"host": "127.0.0.1", "port": 8000, "reload": True},
        "logging": {"level": "DEBUG"},
        "mysql": {
            "host": "127.0.0.1",
            "port": 3306,
            "database": "test_database",
            "username": "test_user",
            "password": "",
            "charset": "utf8mb4",
        },
    }


@pytest.fixture(autouse=True)
def config_dir(monkeypatch, tmp_path, config_data):
    for name in list(os.environ):
        if name.upper().startswith("APP_"):
            monkeypatch.delenv(name)

    get_settings.cache_clear()
    monkeypatch.setattr(settings_module, "__file__", str(tmp_path / "settings.py"))
    (tmp_path / "local.yaml").write_text(
        yaml.safe_dump(config_data), encoding="utf-8"
    )
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
def client(config_dir):
    # Import after configuration isolation so tests never read local secrets.
    from main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
