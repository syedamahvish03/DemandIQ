"""Authentication boundary tests for Supabase-protected processing endpoints."""
from io import BytesIO

from fastapi.testclient import TestClient

import backend.app.main as api_module
from backend.app.main import app, get_current_user

client = TestClient(app)


def _empty_sales_upload():
    return {"file": ("empty.csv", BytesIO(b""), "text/csv")}


def _remove_test_auth_override():
    app.dependency_overrides.pop(get_current_user, None)


def test_processing_endpoint_rejects_requests_without_bearer_token():
    _remove_test_auth_override()
    response = client.post("/api/v1/sales/validate", files=_empty_sales_upload())
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_processing_endpoint_rejects_invalid_supabase_access_token(monkeypatch):
    _remove_test_auth_override()
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")

    class FakeResponse:
        status_code = 401

    class FakeAsyncClient:
        def __init__(self, timeout):
            assert timeout == 5.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url, headers):
            assert url == "https://example.supabase.co/auth/v1/user"
            assert headers["apikey"] == "test-publishable-key"
            assert headers["Authorization"] == "Bearer invalid-token"
            return FakeResponse()

    monkeypatch.setattr(api_module.httpx, "AsyncClient", FakeAsyncClient)
    response = client.post(
        "/api/v1/sales/validate",
        files=_empty_sales_upload(),
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401
    assert "invalid or has expired" in response.json()["detail"]


def test_processing_endpoint_accepts_supabase_verified_user(monkeypatch):
    _remove_test_auth_override()
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"id": "verified-user-id"}

    class FakeAsyncClient:
        def __init__(self, timeout):
            assert timeout == 5.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url, headers):
            assert url == "https://example.supabase.co/auth/v1/user"
            assert headers["Authorization"] == "Bearer valid-test-token"
            return FakeResponse()

    monkeypatch.setattr(api_module.httpx, "AsyncClient", FakeAsyncClient)
    response = client.post(
        "/api/v1/sales/validate",
        files=_empty_sales_upload(),
        headers={"Authorization": "Bearer valid-test-token"},
    )
    # The token was accepted; the request then reaches the normal CSV validation.
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_processing_endpoint_fails_closed_when_supabase_auth_is_unconfigured(monkeypatch):
    _remove_test_auth_override()
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
    response = client.post(
        "/api/v1/sales/validate",
        files=_empty_sales_upload(),
        headers={"Authorization": "Bearer supplied-token"},
    )
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]
