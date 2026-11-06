import pytest
from fastapi.testclient import TestClient


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("base_path", ["", "/", "/workbase-ai", "/api/v1/"])
def test_base_path_applies_to_health_and_documentation(monkeypatch, base_path):
    monkeypatch.setenv("APP_SERVER_BASE_PATH", base_path)
    from main import create_app

    prefix = base_path.rstrip("/")
    with TestClient(create_app()) as client:
        health = client.get(f"{prefix}/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        docs = client.get(f"{prefix}/docs")
        assert docs.status_code == 200
        assert f"{prefix}/openapi.json" in docs.text
        assert client.get(f"{prefix}/redoc").status_code == 200

        schema_response = client.get(f"{prefix}/openapi.json")
        assert schema_response.status_code == 200
        schema = schema_response.json()
        assert "/health" in schema["paths"]
        if prefix:
            assert {"url": prefix} in schema["servers"]
            for path in ["/health", "/docs", "/redoc", "/openapi.json"]:
                assert client.get(path).status_code == 404
