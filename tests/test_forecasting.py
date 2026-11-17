import pandas as pd
import pytest

from forecasting import build_time_features, chronological_baseline_backtest


def sample_daily_sales(days=50):
    dates = pd.date_range("2025-01-01", periods=days, freq="D")
    rows = []
    for store in [1, 2]:
        for item in [101, 102]:
            for index, date in enumerate(dates):
                rows.append({
                    "date": date, "store": store, "item": item,
                    "sales": 10 + index + item % 3 + store,
                })
    return pd.DataFrame(rows)


def test_features_are_created_per_store_item_without_current_day_leakage():
    source = sample_daily_sales()
    features = build_time_features(source)
    row = features.loc[
        (features["store"] == 1)
        & (features["item"] == 101)
        & (features["date"] == pd.Timestamp("2025-01-15"))
    ].iloc[0]

    assert row["lag_1"] == 26
    assert row["lag_7"] == 20
    assert row["lag_14"] == 13
    assert row["rolling_mean_7"] == pytest.approx(23)
    assert row["day_of_week"] == 2


def test_backtest_uses_last_dates_and_returns_baseline_metrics():
    metrics, predictions, metadata = chronological_baseline_backtest(
        sample_daily_sales(), holdout_days=7
    )

    assert set(metrics["model"]) == {"seasonal_naive_7", "moving_average_7"}
    assert len(predictions) == 7 * 4
    assert metadata["test_rows"] == 28
    assert metadata["holdout_start"].isoformat() == "2025-02-13"
    assert metrics["WAPE (%)"].notna().all()


def test_backtest_rejects_too_short_history():
    with pytest.raises(ValueError, match="Not enough distinct dates"):
        chronological_baseline_backtest(sample_daily_sales(days=10), holdout_days=10)


def test_feature_builder_rejects_missing_columns():
    with pytest.raises(ValueError, match="Missing required columns"):
        build_time_features(pd.DataFrame({"date": ["2025-01-01"]}))
