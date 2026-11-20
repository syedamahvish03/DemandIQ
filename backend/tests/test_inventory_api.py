"""Integration tests for the inventory API workflow."""
from io import BytesIO

import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import MAX_UPLOAD_BYTES, app

client = TestClient(app)


def sales_csv(days: int = 35) -> bytes:
    dates = pd.date_range("2025-01-01", periods=days, freq="D")
    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "store": ["STORE_A"] * days,
        "item": ["SKU_100"] * days,
        "sales": [10 + (i % 4) for i in range(days)],
    }).to_csv(index=False).encode("utf-8")


def inventory_csv() -> bytes:
    return pd.DataFrame([{
        "store": "STORE_A", "item": "SKU_100", "on_hand": 12,
        "on_order": 4, "backorders": 0, "lead_time_days": 3,
        "review_period_days": 7,
    }]).to_csv(index=False).encode("utf-8")


def test_inventory_template_returns_one_blank_row_for_sales_pair():
    response = client.post(
        "/api/v1/inventory/template",
        files={"sales_file": ("sales.csv", BytesIO(sales_csv()), "text/csv")},
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    template = pd.read_csv(BytesIO(response.content))
    assert list(template.columns) == [
        "store", "item", "on_hand", "on_order", "backorders",
        "lead_time_days", "review_period_days",
    ]
    assert len(template) == 1
    assert pd.isna(template.loc[0, "on_hand"])


def test_inventory_recommendations_use_explicit_stock_inputs():
    response = client.post(
        "/api/v1/inventory/recommendations",
        files={
            "sales_file": ("sales.csv", BytesIO(sales_csv()), "text/csv"),
            "inventory_file": ("inventory.csv", BytesIO(inventory_csv()), "text/csv"),
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["metadata"]["complete_recommendations"] == 1
    assert len(payload["recommendations"]) == 1
    row = payload["recommendations"][0]
    assert row["on_hand"] == 12
    assert row["inventory_position"] == 16
    assert row["recommended_order_qty"] >= 0
    assert row["demand_basis"] == "historical_average"


def test_inventory_recommendations_reject_missing_columns():
    invalid_inventory = b"store,item,on_hand\nSTORE_A,SKU_100,10\n"
    response = client.post(
        "/api/v1/inventory/recommendations",
        files={
            "sales_file": ("sales.csv", BytesIO(sales_csv()), "text/csv"),
            "inventory_file": ("inventory.csv", BytesIO(invalid_inventory), "text/csv"),
        },
    )
    assert response.status_code == 422
    assert "missing required columns" in response.json()["detail"].lower()


def test_inventory_recommendations_reject_negative_stock():
    invalid = pd.DataFrame([{
        "store": "STORE_A", "item": "SKU_100", "on_hand": -1,
        "on_order": 0, "backorders": 0, "lead_time_days": 3,
        "review_period_days": 7,
    }]).to_csv(index=False).encode("utf-8")
    response = client.post(
        "/api/v1/inventory/recommendations",
        files={
            "sales_file": ("sales.csv", BytesIO(sales_csv()), "text/csv"),
            "inventory_file": ("inventory.csv", BytesIO(invalid), "text/csv"),
        },
    )
    assert response.status_code == 422
    assert "cannot be negative" in response.json()["detail"]



def test_inventory_template_rejects_sales_upload_over_size_limit():
    oversized_csv = b"x" * (MAX_UPLOAD_BYTES + 1)
    response = client.post(
        "/api/v1/inventory/template",
        files={"sales_file": ("sales.csv", BytesIO(oversized_csv), "text/csv")},
    )

    assert response.status_code == 413
    assert "10 MB upload limit" in response.json()["detail"]


def test_inventory_recommendations_reject_oversized_sales_upload():
    oversized_csv = b"x" * (MAX_UPLOAD_BYTES + 1)
    response = client.post(
        "/api/v1/inventory/recommendations",
        files={
            "sales_file": ("sales.csv", BytesIO(oversized_csv), "text/csv"),
            "inventory_file": ("inventory.csv", BytesIO(inventory_csv()), "text/csv"),
        },
    )

    assert response.status_code == 413
    assert "10 MB upload limit" in response.json()["detail"]


def test_inventory_recommendations_reject_oversized_inventory_upload():
    oversized_csv = b"x" * (MAX_UPLOAD_BYTES + 1)
    response = client.post(
        "/api/v1/inventory/recommendations",
        files={
            "sales_file": ("sales.csv", BytesIO(sales_csv()), "text/csv"),
            "inventory_file": ("inventory.csv", BytesIO(oversized_csv), "text/csv"),
        },
    )

    assert response.status_code == 413
    assert "10 MB upload limit" in response.json()["detail"]
