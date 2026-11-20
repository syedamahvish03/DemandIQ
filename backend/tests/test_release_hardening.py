"""Stage 6 API boundary and upload hardening regression tests."""
from io import BytesIO

from fastapi.testclient import TestClient

from backend.app.main import app, get_allowed_origins

client = TestClient(app)


def test_cors_preflight_allows_configured_local_frontend_origin():
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_preflight_does_not_allow_unconfigured_origin():
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_configured_cors_origins_are_trimmed_and_empty_entries_removed(monkeypatch):
    monkeypatch.setenv(
        "DEMANDIQ_CORS_ORIGINS",
        " https://app.example , , https://preview.example/ ",
    )

    assert get_allowed_origins() == [
        "https://app.example",
        "https://preview.example",
    ]


def test_empty_forecast_upload_returns_client_error():
    response = client.post(
        "/api/v1/forecasts",
        files={"file": ("empty.csv", BytesIO(b""), "text/csv")},
        data={"horizon_days": "7"},
    )

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_empty_sales_validation_upload_returns_client_error():
    response = client.post(
        "/api/v1/sales/validate",
        files={"file": ("empty.csv", BytesIO(b""), "text/csv")},
    )

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_inventory_template_rejects_non_csv_and_empty_uploads():
    wrong_extension = client.post(
        "/api/v1/inventory/template",
        files={"sales_file": ("sales.txt", b"not a csv", "text/plain")},
    )
    empty_file = client.post(
        "/api/v1/inventory/template",
        files={"sales_file": ("sales.csv", BytesIO(b""), "text/csv")},
    )

    assert wrong_extension.status_code == 415
    assert empty_file.status_code == 400
    assert "empty" in empty_file.json()["detail"].lower()


def test_inventory_recommendations_reject_non_csv_and_empty_inventory_uploads():
    from tests_helpers import make_sales_csv_for_hardening

    sales = ("sales.csv", BytesIO(make_sales_csv_for_hardening()), "text/csv")
    wrong_extension = client.post(
        "/api/v1/inventory/recommendations",
        files={
            "sales_file": sales,
            "inventory_file": ("inventory.txt", b"not a csv", "text/plain"),
        },
    )

    empty_inventory = client.post(
        "/api/v1/inventory/recommendations",
        files={
            "sales_file": ("sales.csv", BytesIO(make_sales_csv_for_hardening()), "text/csv"),
            "inventory_file": ("inventory.csv", BytesIO(b""), "text/csv"),
        },
    )

    assert wrong_extension.status_code == 415
    assert empty_inventory.status_code == 400
    assert "empty" in empty_inventory.json()["detail"].lower()
