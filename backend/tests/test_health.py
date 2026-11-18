"""Smoke and integration tests for the DemandIQ API."""
from io import BytesIO

import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_endpoint_returns_service_status():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "service": "DemandIQ API",
        "status": "ok",
        "version": "0.2.0",
    }


def test_root_endpoint_exposes_api_documentation_path():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "DemandIQ API"
    assert response.json()["docs"] == "/docs"


def make_sales_csv(days: int = 50) -> bytes:
    dates = pd.date_range("2025-01-01", periods=days, freq="D")
    frame = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "store": [1] * days,
        "item": [101] * days,
        "sales": [20 + (index % 7) for index in range(days)],
    })
    return frame.to_csv(index=False).encode("utf-8")


def test_forecast_endpoint_returns_real_model_predictions():
    response = client.post(
        "/api/v1/forecasts",
        files={"file": ("sales.csv", BytesIO(make_sales_csv()), "text/csv")},
        data={"horizon_days": "7"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["model"] == "random_forest"
    assert payload["metadata"]["horizon_days"] == 7
    assert payload["metadata"]["series_count"] == 1
    assert len(payload["forecast"]) == 7
    assert all(row["forecast_sales"] >= 0 for row in payload["forecast"])
    assert payload["quality_report"]["rows_valid"] == 50


def test_forecast_endpoint_rejects_non_csv_files():
    response = client.post(
        "/api/v1/forecasts",
        files={"file": ("sales.txt", b"not a csv", "text/plain")},
        data={"horizon_days": "7"},
    )
    assert response.status_code == 415


def test_forecast_endpoint_rejects_unsupported_horizon():
    response = client.post(
        "/api/v1/forecasts",
        files={"file": ("sales.csv", BytesIO(make_sales_csv()), "text/csv")},
        data={"horizon_days": "10"},
    )
    assert response.status_code == 422
    assert "7, 15 or 30" in response.json()["detail"]


def test_forecast_endpoint_reports_invalid_csv_columns():
    invalid_csv = b"date,units\n2025-01-01,10\n"
    response = client.post(
        "/api/v1/forecasts",
        files={"file": ("sales.csv", BytesIO(invalid_csv), "text/csv")},
        data={"horizon_days": "7"},
    )
    assert response.status_code == 422
    assert "quality_report" in response.json()["detail"]
