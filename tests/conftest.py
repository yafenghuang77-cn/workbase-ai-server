import os

import pytest
from fastapi.testclient import TestClient

import config.settings as settings_module
from config.settings import get_settings


@pytest.fixture
def env_content():
    return """APP_SERVER_HOST=127.0.0.1
APP_SERVER_PORT=8000
APP_SERVER_RELOAD=true
APP_SERVER_BASE_PATH=
APP_LOGGING_LEVEL=DEBUG
APP_MYSQL_HOST=127.0.0.1
APP_MYSQL_PORT=3306
APP_MYSQL_DATABASE=test_database
APP_MYSQL_USERNAME=test_user
APP_MYSQL_PASSWORD=
APP_MYSQL_CHARSET=utf8mb4
APP_LLM_MODEL=
APP_LLM_API_KEY=
APP_LLM_BASE_URL=
"""


@pytest.fixture(autouse=True)
def config_dir(monkeypatch, tmp_path, env_content):
    for name in list(os.environ):
        if name.upper().startswith("APP_"):
            monkeypatch.delenv(name)
    get_settings.cache_clear()
    monkeypatch.setattr(settings_module, "CONFIG_DIR", tmp_path)
    (tmp_path / ".env.local").write_text(env_content, encoding="utf-8")
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
def client(config_dir):
    # Import after configuration isolation so tests never read local secrets.
    from main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
