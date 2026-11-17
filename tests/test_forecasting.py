import pandas as pd
import pytest

from forecasting import (
    build_time_features,
    chronological_baseline_backtest,
    evaluate_random_forest,
)


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


def test_random_forest_uses_chronological_holdout_and_returns_metrics():
    metrics, predictions, metadata = evaluate_random_forest(
        sample_daily_sales(), holdout_days=7, max_train_rows=100
    )

    assert metrics.loc[0, "model"] == "random_forest"
    assert len(predictions) == 7 * 4
    assert metadata["test_rows"] == 28
    assert metadata["train_rows_used"] <= 100
    assert metadata["holdout_start"].isoformat() == "2025-02-13"
    assert predictions["random_forest"].ge(0).all()
    assert metrics[["MAE", "RMSE", "WAPE (%)", "Bias (%)"]].notna().all().all()


def test_random_forest_rejects_invalid_training_cap():
    with pytest.raises(ValueError, match="max_train_rows"):
        evaluate_random_forest(sample_daily_sales(), holdout_days=7, max_train_rows=0)


def test_future_forecast_returns_requested_horizon_per_store_item():
    from forecasting import forecast_future_demand

    forecast, metadata = forecast_future_demand(sample_daily_sales(days=50), horizon_days=7)

    assert len(forecast) == 7 * 4
    assert forecast.groupby(["store", "item"]).size().eq(7).all()
    assert metadata["series_count"] == 4
    assert metadata["horizon_days"] == 7
    assert forecast["forecast_sales"].ge(0).all()
    assert forecast["date"].min() == pd.Timestamp("2025-02-20")


def test_future_forecast_rejects_unsupported_horizon():
    from forecasting import forecast_future_demand

    with pytest.raises(ValueError, match="7, 15 or 30"):
        forecast_future_demand(sample_daily_sales(), horizon_days=10)


def test_future_forecast_rejects_irregular_daily_series():
    from forecasting import forecast_future_demand

    source = sample_daily_sales()
    source = source.drop(source.index[5])

    with pytest.raises(ValueError, match="missing or irregular dates"):
        forecast_future_demand(source, horizon_days=7)


def test_future_forecast_rejects_duplicate_daily_series_rows():
    from forecasting import forecast_future_demand

    source = sample_daily_sales()
    source = pd.concat([source, source.iloc[[0]]], ignore_index=True)

    with pytest.raises(ValueError, match="one sales row per date"):
        forecast_future_demand(source, horizon_days=7)
