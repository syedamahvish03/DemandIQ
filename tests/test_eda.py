import pandas as pd
import pytest

from eda import daily_sales, store_sales, summarize_sales_data, top_products, weekday_sales


@pytest.fixture
def sample_sales():
    return pd.DataFrame({
        "date": pd.to_datetime(["2025-01-06", "2025-01-06", "2025-01-07", "2025-01-12"]),
        "store": [1, 2, 1, 1],
        "item": [101, 101, 102, 101],
        "sales": [10, 5, 8, 7],
    })


def test_summary_reports_core_metrics(sample_sales):
    result = summarize_sales_data(sample_sales)
    assert result["rows"] == 4
    assert result["products"] == 2
    assert result["stores"] == 2
    assert result["total_units"] == 30
    assert result["days_covered"] == 3
    assert result["date_start"].isoformat() == "2025-01-06"


def test_daily_sales_aggregates_same_date(sample_sales):
    result = daily_sales(sample_sales)
    assert result["sales"].tolist() == [15, 8, 7]
    assert len(result) == 3


def test_top_products_and_store_sales_are_ranked(sample_sales):
    products = top_products(sample_sales, limit=1)
    stores = store_sales(sample_sales)
    assert products.iloc[0]["item"] == 101
    assert products.iloc[0]["sales"] == 22
    assert stores.iloc[0]["store"] == 1
    assert stores.iloc[0]["sales"] == 25


def test_weekday_sales_uses_monday_to_sunday_order(sample_sales):
    result = weekday_sales(sample_sales)
    assert result["weekday"].astype(str).tolist() == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    assert result.loc[result["weekday"].astype(str) == "Monday", "sales"].iloc[0] == 7.5


def test_empty_data_returns_empty_summary():
    empty = pd.DataFrame(columns=["date", "store", "item", "sales"])
    assert summarize_sales_data(empty)["rows"] == 0
    assert daily_sales(empty).empty
    assert top_products(empty).empty


def test_invalid_limit_is_rejected(sample_sales):
    with pytest.raises(ValueError):
        top_products(sample_sales, limit=0)
