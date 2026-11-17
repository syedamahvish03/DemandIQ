import pandas as pd
import pytest

from inventory import (
    build_inventory_template,
    calculate_inventory_recommendations,
)


def sales_fixture():
    dates = pd.date_range("2025-01-01", periods=28, freq="D")
    return pd.DataFrame({
        "date": list(dates) * 2,
        "store": [1] * 28 + [1] * 28,
        "item": [101] * 28 + [102] * 28,
        "sales": [10] * 28 + list(range(1, 29)),
    })


def inventory_fixture():
    return pd.DataFrame([{
        "store": 1, "item": 101, "on_hand": 20, "on_order": 5,
        "backorders": 0, "lead_time_days": 3, "review_period_days": 7,
    }])


def test_template_creates_one_blank_row_per_store_item():
    template = build_inventory_template(sales_fixture())
    assert len(template) == 2
    assert set(template.columns) == {
        "store", "item", "on_hand", "on_order", "backorders",
        "lead_time_days", "review_period_days",
    }
    assert template["on_hand"].isna().all()


def test_inventory_math_uses_user_stock_inputs_and_recent_sales():
    result, metadata = calculate_inventory_recommendations(
        sales_fixture(), inventory_fixture()
    )
    row = result.iloc[0]

    assert row["avg_daily_demand"] == pytest.approx(10)
    assert row["daily_demand_std"] == pytest.approx(0)
    assert row["safety_stock"] == pytest.approx(0)
    assert row["reorder_point"] == pytest.approx(30)
    assert row["inventory_position"] == pytest.approx(25)
    assert row["target_stock"] == pytest.approx(100)
    assert row["recommended_order_qty"] == 75
    assert bool(row["reorder_required"]) is True
    assert metadata["complete_recommendations"] == 1


def test_incomplete_stock_inputs_are_excluded_not_guessed():
    incomplete = inventory_fixture()
    incomplete.loc[0, "on_hand"] = None
    result, metadata = calculate_inventory_recommendations(sales_fixture(), incomplete)

    assert result.empty
    assert metadata["excluded_input_rows"] == 1


def test_duplicate_inventory_pairs_are_rejected():
    duplicate = pd.concat([inventory_fixture(), inventory_fixture()], ignore_index=True)
    with pytest.raises(ValueError, match="one row per store-item"):
        calculate_inventory_recommendations(sales_fixture(), duplicate)


def test_negative_stock_values_are_rejected():
    invalid = inventory_fixture()
    invalid.loc[0, "on_hand"] = -1
    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_inventory_recommendations(sales_fixture(), invalid)


def test_zero_lead_time_is_rejected():
    invalid = inventory_fixture()
    invalid.loc[0, "lead_time_days"] = 0
    with pytest.raises(ValueError, match="greater than zero"):
        calculate_inventory_recommendations(sales_fixture(), invalid)



def test_illustrative_inputs_are_derived_from_sales_and_labelled_by_settings():
    from inventory import build_illustrative_inventory_inputs

    result = build_illustrative_inventory_inputs(
        sales_fixture(), stock_cover_days=5, lead_time_days=4, review_period_days=6
    )
    row = result.loc[result["item"] == 101].iloc[0]
    assert row["on_hand"] == 50
    assert row["on_order"] == 0
    assert row["backorders"] == 0
    assert row["lead_time_days"] == 4
    assert row["review_period_days"] == 6


def test_illustrative_inputs_reject_zero_assumption():
    from inventory import build_illustrative_inventory_inputs

    with pytest.raises(ValueError, match="at least 1 day"):
        build_illustrative_inventory_inputs(sales_fixture(), stock_cover_days=0)



def test_forecast_demand_drives_reorder_point_and_target_stock():
    forecast = pd.DataFrame({
        "date": list(pd.date_range("2025-01-29", periods=10, freq="D")),
        "store": [1] * 10,
        "item": [101] * 10,
        "forecast_sales": [20.0] * 10,
    })
    result, metadata = calculate_inventory_recommendations(
        sales_fixture(),
        inventory_fixture(),
        demand_forecast=forecast,
    )
    row = result.iloc[0]

    assert row["forecast_lead_demand"] == pytest.approx(60)
    assert row["forecast_protection_demand"] == pytest.approx(200)
    assert row["reorder_point"] == pytest.approx(60)
    assert row["target_stock"] == pytest.approx(200)
    assert row["recommended_order_qty"] == 175
    assert row["demand_basis"] == "future_forecast"
    assert metadata["demand_basis"] == "future_forecast"


def test_forecast_inventory_requires_full_lead_plus_review_horizon():
    forecast = pd.DataFrame({
        "date": pd.date_range("2025-01-29", periods=9, freq="D"),
        "store": [1] * 9,
        "item": [101] * 9,
        "forecast_sales": [20.0] * 9,
    })
    with pytest.raises(ValueError, match="At least 10 forecast days are required"):
        calculate_inventory_recommendations(
            sales_fixture(),
            inventory_fixture(),
            demand_forecast=forecast,
        )


def test_forecast_inventory_rejects_duplicate_daily_predictions():
    forecast = pd.DataFrame({
        "date": [pd.Timestamp("2025-01-29"), pd.Timestamp("2025-01-29")],
        "store": [1, 1],
        "item": [101, 101],
        "forecast_sales": [20.0, 21.0],
    })
    with pytest.raises(ValueError, match="one row per date"):
        calculate_inventory_recommendations(
            sales_fixture(),
            inventory_fixture(),
            demand_forecast=forecast,
        )
