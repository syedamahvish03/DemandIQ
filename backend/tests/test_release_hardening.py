"""Stage 6 API boundary and upload hardening regression tests."""
from io import BytesIO

from fastapi.testclient import TestClient

import backend.app.main as api_module
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
    import pandas as pd

    dates = pd.date_range("2025-01-01", periods=35, freq="D")
    frame = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "store": ["STORE_A"] * 35,
        "item": ["SKU_100"] * 35,
        "sales": [10 + (index % 4) for index in range(35)],
    })
    sales_bytes = frame.to_csv(index=False).encode("utf-8")
    sales = ("sales.csv", BytesIO(sales_bytes), "text/csv")
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
            "sales_file": ("sales.csv", BytesIO(sales_bytes), "text/csv"),
            "inventory_file": ("inventory.csv", BytesIO(b""), "text/csv"),
        },
    )

    assert wrong_extension.status_code == 415
    assert empty_inventory.status_code == 400
    assert "empty" in empty_inventory.json()["detail"].lower()


def test_processing_api_rate_limit_returns_429_and_retry_after(monkeypatch):
    monkeypatch.setenv("DEMANDIQ_API_RATE_LIMIT_REQUESTS", "2")
    monkeypatch.setenv("DEMANDIQ_API_RATE_LIMIT_WINDOW_SECONDS", "60")
    with api_module._rate_limit_lock:
        api_module._rate_limit_buckets.clear()

    first = client.post(
        "/api/v1/sales/validate",
        files={"file": ("empty.csv", BytesIO(b""), "text/csv")},
    )
    second = client.post(
        "/api/v1/sales/validate",
        files={"file": ("empty.csv", BytesIO(b""), "text/csv")},
    )
    limited = client.post(
        "/api/v1/sales/validate",
        files={"file": ("empty.csv", BytesIO(b""), "text/csv")},
    )

    assert first.status_code == 400
    assert second.status_code == 400
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1
    assert "Too many processing requests" in limited.json()["detail"]

    # The limit is scoped to processing endpoints, not the health check.
    assert client.get("/api/v1/health").status_code == 200
    with api_module._rate_limit_lock:
        api_module._rate_limit_buckets.clear()


def test_rate_limiter_does_not_clear_active_clients_when_capacity_is_full(monkeypatch):
    monkeypatch.setenv("DEMANDIQ_API_RATE_LIMIT_REQUESTS", "10")
    monkeypatch.setenv("DEMANDIQ_API_RATE_LIMIT_WINDOW_SECONDS", "60")
    now = api_module.time.monotonic()
    with api_module._rate_limit_lock:
        api_module._rate_limit_buckets.clear()
        api_module._rate_limit_buckets.update({
            f"active-client-{index}": (now, 1)
            for index in range(5000)
        })

    response = client.post(
        "/api/v1/sales/validate",
        files={"file": ("empty.csv", BytesIO(b""), "text/csv")},
    )

    assert response.status_code == 429
    assert "capacity" in response.json()["detail"].lower()
    with api_module._rate_limit_lock:
        assert len(api_module._rate_limit_buckets) == 5000
        assert "active-client-0" in api_module._rate_limit_buckets
        api_module._rate_limit_buckets.clear()


def test_rate_limiter_prunes_expired_clients_before_rejecting_new_client(monkeypatch):
    monkeypatch.setenv("DEMANDIQ_API_RATE_LIMIT_REQUESTS", "10")
    monkeypatch.setenv("DEMANDIQ_API_RATE_LIMIT_WINDOW_SECONDS", "60")
    expired_at = api_module.time.monotonic() - 120
    with api_module._rate_limit_lock:
        api_module._rate_limit_buckets.clear()
        api_module._rate_limit_buckets.update({
            f"expired-client-{index}": (expired_at, 1)
            for index in range(5000)
        })

    response = client.post(
        "/api/v1/sales/validate",
        files={"file": ("empty.csv", BytesIO(b""), "text/csv")},
    )

    assert response.status_code == 400
    with api_module._rate_limit_lock:
        assert len(api_module._rate_limit_buckets) == 1
        assert "testclient" in api_module._rate_limit_buckets
        api_module._rate_limit_buckets.clear()


def test_all_upload_endpoints_enforce_per_file_size_limit(monkeypatch):
    monkeypatch.setattr(api_module, "MAX_UPLOAD_BYTES", 8)
    oversized = b"123456789"

    forecast = client.post(
        "/api/v1/forecasts",
        files={"file": ("sales.csv", oversized, "text/csv")},
        data={"horizon_days": "7"},
    )
    sales_validation = client.post(
        "/api/v1/sales/validate",
        files={"file": ("sales.csv", oversized, "text/csv")},
    )
    inventory_template = client.post(
        "/api/v1/inventory/template",
        files={"sales_file": ("sales.csv", oversized, "text/csv")},
    )
    inventory_sales_oversized = client.post(
        "/api/v1/inventory/recommendations",
        files={
            "sales_file": ("sales.csv", oversized, "text/csv"),
            "inventory_file": ("inventory.csv", b"x", "text/csv"),
        },
    )
    inventory_stock_oversized = client.post(
        "/api/v1/inventory/recommendations",
        files={
            "sales_file": ("sales.csv", b"x", "text/csv"),
            "inventory_file": ("inventory.csv", oversized, "text/csv"),
        },
    )

    assert [
        forecast.status_code,
        sales_validation.status_code,
        inventory_template.status_code,
        inventory_sales_oversized.status_code,
        inventory_stock_oversized.status_code,
    ] == [413, 413, 413, 413, 413]


def test_forecast_unexpected_error_returns_generic_message_without_exception_details(monkeypatch):
    import pandas as pd

    dates = pd.date_range("2025-01-01", periods=35, freq="D")
    frame = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "store": ["STORE_A"] * 35,
        "item": ["SKU_100"] * 35,
        "sales": [10 + (index % 4) for index in range(35)],
    })
    monkeypatch.setattr(
        api_module,
        "forecast_future_demand",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("private-row-secret")),
    )

    response = client.post(
        "/api/v1/forecasts",
        files={"file": ("sales.csv", frame.to_csv(index=False).encode("utf-8"), "text/csv")},
        data={"horizon_days": "7"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "The forecast could not be generated due to an internal processing error."
    )
    assert "private-row-secret" not in response.text
    assert "Traceback" not in response.text
