"""Smoke tests for the DemandIQ API foundation."""
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_endpoint_returns_service_status():
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "DemandIQ API",
        "status": "ok",
        "version": "0.1.0",
    }


def test_root_endpoint_exposes_api_documentation_path():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["service"] == "DemandIQ API"
    assert response.json()["docs"] == "/docs"
