"""Smoke and integration tests for the DemandIQ API."""
from io import BytesIO

import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import MAX_UPLOAD_BYTES, app

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


def make_inventory_csv(lead_time_days: int = 3, review_period_days: int = 7) -> bytes:
    frame = pd.DataFrame([{
        "store": 1,
        "item": 101,
        "on_hand": 50,
        "on_order": 0,
        "backorders": 0,
        "lead_time_days": lead_time_days,
        "review_period_days": review_period_days,
    }])
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


def test_inventory_recommendations_use_future_demand_forecast():
    response = client.post(
        "/api/v1/inventory/recommendations",
        files={
            "sales_file": ("sales.csv", BytesIO(make_sales_csv()), "text/csv"),
            "inventory_file": ("inventory.csv", BytesIO(make_inventory_csv()), "text/csv"),
        },
        data={"forecast_horizon_days": "15"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["demand_basis"] == "future_forecast"
    assert payload["metadata"]["forecast_horizon_days"] == 15
    assert payload["metadata"]["forecast_rows"] == 15
    assert len(payload["recommendations"]) == 1
    recommendation = payload["recommendations"][0]
    assert recommendation["demand_basis"] == "future_forecast"
    assert recommendation["forecast_lead_demand"] >= 0
    assert recommendation["forecast_protection_demand"] >= recommendation["forecast_lead_demand"]
    assert recommendation["recommended_order_qty"] >= 0


def test_inventory_recommendations_reject_insufficient_forecast_horizon():
    response = client.post(
        "/api/v1/inventory/recommendations",
        files={
            "sales_file": ("sales.csv", BytesIO(make_sales_csv()), "text/csv"),
            "inventory_file": ("inventory.csv", BytesIO(make_inventory_csv()), "text/csv"),
        },
        data={"forecast_horizon_days": "7"},
    )

    assert response.status_code == 422
    assert "Forecast horizon is too short" in response.json()["detail"]


def test_inventory_recommendations_reject_unsupported_forecast_horizon():
    response = client.post(
        "/api/v1/inventory/recommendations",
        files={
            "sales_file": ("sales.csv", BytesIO(make_sales_csv()), "text/csv"),
            "inventory_file": ("inventory.csv", BytesIO(make_inventory_csv()), "text/csv"),
        },
        data={"forecast_horizon_days": "10"},
    )

    assert response.status_code == 422
    assert "7, 15 or 30" in response.json()["detail"]



def test_forecast_endpoint_rejects_upload_over_size_limit():
    oversized_csv = b"x" * (MAX_UPLOAD_BYTES + 1)
    response = client.post(
        "/api/v1/forecasts",
        files={"file": ("sales.csv", BytesIO(oversized_csv), "text/csv")},
        data={"horizon_days": "7"},
    )

    assert response.status_code == 413
    assert "10 MB upload limit" in response.json()["detail"]



def test_forecast_endpoint_accepts_mixed_date_representations():
    dates = pd.date_range("2025-01-01", periods=50, freq="D")
    frame = pd.DataFrame({
        "date": [
            date.strftime("%Y-%m-%d") if index % 2 == 0
            else date.strftime("%Y-%m-%d %H:%M:%S")
            for index, date in enumerate(dates)
        ],
        "store": ["STORE_A"] * 50,
        "item": ["SKU_100"] * 50,
        "sales": [20 + (index % 7) for index in range(50)],
    })
    response = client.post(
        "/api/v1/forecasts",
        files={
            "file": (
                "mixed_dates.csv",
                BytesIO(frame.to_csv(index=False).encode("utf-8")),
                "text/csv",
            )
        },
        data={"horizon_days": "7"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["quality_report"]["rows_valid"] == 50
    assert len(payload["forecast"]) == 7


def test_forecast_endpoint_rejects_invalid_text_encoding():
    response = client.post(
        "/api/v1/forecasts",
        files={"file": ("sales.csv", BytesIO(b"date,store,item,sales\n\xff"), "text/csv")},
        data={"horizon_days": "7"},
    )

    assert response.status_code == 400
    assert "valid CSV" in response.json()["detail"]
