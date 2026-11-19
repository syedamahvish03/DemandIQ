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


def test_recursive_multi_horizon_backtest_compares_models_at_all_horizons():
    from forecasting import recursive_multi_horizon_backtest

    metrics, predictions, metadata = recursive_multi_horizon_backtest(
        sample_daily_sales(days=60), max_train_rows=100
    )

    assert set(metrics["model"]) == {
        "seasonal_naive_7", "moving_average_7", "random_forest"
    }
    assert set(metrics["horizon_days"]) == {7, 15, 30}
    assert len(metrics) == 9
    assert len(predictions) == 30 * 4 * 3
    assert metadata["holdout_days"] == 30
    assert metadata["series_count"] == 4
    assert metadata["training_rows_used"] <= 100
    assert metadata["evaluation_method"] == "recursive_multi_step"
    assert metrics[["MAE", "RMSE", "WAPE (%)", "Bias (%)"]].notna().all().all()


def test_recursive_multi_horizon_backtest_rejects_duplicate_daily_rows():
    from forecasting import recursive_multi_horizon_backtest

    source = sample_daily_sales(days=60)
    source = pd.concat([source, source.iloc[[0]]], ignore_index=True)

    with pytest.raises(ValueError, match="one sales row per date"):
        recursive_multi_horizon_backtest(source)


def test_recursive_multi_horizon_backtest_rejects_irregular_series():
    from forecasting import recursive_multi_horizon_backtest

    source = sample_daily_sales(days=60).drop(index=5)

    with pytest.raises(ValueError, match="missing or irregular dates"):
        recursive_multi_horizon_backtest(source)


def test_recursive_multi_horizon_backtest_rejects_insufficient_history():
    from forecasting import recursive_multi_horizon_backtest

    with pytest.raises(ValueError, match="at least 30 distinct dates"):
        recursive_multi_horizon_backtest(sample_daily_sales(days=29))


def test_recursive_multi_horizon_backtest_rejects_invalid_training_cap():
    from forecasting import recursive_multi_horizon_backtest

    with pytest.raises(ValueError, match="max_train_rows"):
        recursive_multi_horizon_backtest(sample_daily_sales(days=60), max_train_rows=0)


def test_recursive_multi_horizon_predictions_do_not_use_holdout_actuals():
    from forecasting import recursive_multi_horizon_backtest

    source = sample_daily_sales(days=60)
    changed_holdout = source.copy()
    final_date = changed_holdout["date"].max()
    changed_holdout.loc[changed_holdout["date"] > final_date - pd.Timedelta(days=30), "sales"] += 10_000

    _, original_predictions, _ = recursive_multi_horizon_backtest(source)
    _, changed_predictions, _ = recursive_multi_horizon_backtest(changed_holdout)

    comparison_columns = ["date", "store", "item", "model", "forecast_step", "prediction"]
    pd.testing.assert_frame_equal(
        original_predictions[comparison_columns],
        changed_predictions[comparison_columns],
    )


def test_rolling_origin_backtest_evaluates_multiple_origins_and_horizons():
    from forecasting import rolling_origin_multi_horizon_backtest

    metrics, predictions, metadata = rolling_origin_multi_horizon_backtest(
        sample_daily_sales(days=90), n_origins=3, step_days=15, max_train_rows=100
    )

    assert len(metrics) == 9
    assert set(metrics["model"]) == {
        "seasonal_naive_7", "moving_average_7", "random_forest"
    }
    assert set(metrics["horizon_days"]) == {7, 15, 30}
    assert metrics["origins_evaluated"].eq(3).all()
    assert metrics["WAPE_std_across_origins (%)"].notna().all()
    assert predictions["origin"].nunique() == 3
    assert len(predictions) == 3 * 30 * 4 * 3
    assert metadata["origins_evaluated"] == 3
    assert metadata["origin_spacing_days"] == 15
    assert metadata["holdout_days_per_origin"] == 30
    assert metadata["evaluation_method"] == "rolling_origin_recursive_multi_step"


def test_rolling_origin_backtest_predictions_do_not_use_each_origin_holdout_actuals():
    from forecasting import rolling_origin_multi_horizon_backtest

    source = sample_daily_sales(days=90)
    changed_holdouts = source.copy()
    final_date = changed_holdouts["date"].max()
    changed_holdouts.loc[
        changed_holdouts["date"] > final_date - pd.Timedelta(days=30), "sales"
    ] += 10_000

    _, original_predictions, _ = rolling_origin_multi_horizon_backtest(source)
    _, changed_predictions, _ = rolling_origin_multi_horizon_backtest(changed_holdouts)

    comparison_columns = [
        "origin", "origin_number", "date", "store", "item",
        "model", "forecast_step", "prediction",
    ]
    pd.testing.assert_frame_equal(
        original_predictions[comparison_columns],
        changed_predictions[comparison_columns],
    )


def test_rolling_origin_backtest_rejects_insufficient_history():
    from forecasting import rolling_origin_multi_horizon_backtest

    with pytest.raises(ValueError, match="At least 76 distinct daily dates"):
        rolling_origin_multi_horizon_backtest(sample_daily_sales(days=75))


def test_rolling_origin_backtest_rejects_invalid_origin_count():
    from forecasting import rolling_origin_multi_horizon_backtest

    with pytest.raises(ValueError, match="n_origins must be at least 2"):
        rolling_origin_multi_horizon_backtest(
            sample_daily_sales(days=90), n_origins=1
        )


def test_rolling_origin_backtest_rejects_duplicate_daily_rows():
    from forecasting import rolling_origin_multi_horizon_backtest

    source = sample_daily_sales(days=90)
    source = pd.concat([source, source.iloc[[0]]], ignore_index=True)

    with pytest.raises(ValueError, match="one sales row per date"):
        rolling_origin_multi_horizon_backtest(source)


def test_rolling_origin_backtest_rejects_irregular_daily_series():
    from forecasting import rolling_origin_multi_horizon_backtest

    source = sample_daily_sales(days=90).drop(index=10)

    with pytest.raises(ValueError, match="missing or irregular dates"):
        rolling_origin_multi_horizon_backtest(source, n_origins=3, step_days=15)


def test_rolling_origin_backtest_rejects_non_positive_step():
    from forecasting import rolling_origin_multi_horizon_backtest

    with pytest.raises(ValueError, match="step_days must be at least 1"):
        rolling_origin_multi_horizon_backtest(
            sample_daily_sales(days=90), n_origins=3, step_days=0
        )


def test_rolling_origin_backtest_rejects_invalid_training_cap():
    from forecasting import rolling_origin_multi_horizon_backtest

    with pytest.raises(ValueError, match="max_train_rows must be at least 1"):
        rolling_origin_multi_horizon_backtest(
            sample_daily_sales(days=90), n_origins=3, max_train_rows=0
        )


def test_feature_builder_rejects_non_finite_sales():
    source = sample_daily_sales()
    source["sales"] = source["sales"].astype(float)
    source.loc[source.index[0], "sales"] = float("inf")

    with pytest.raises(ValueError, match="finite numbers"):
        build_time_features(source)


def test_feature_builder_rejects_negative_sales():
    source = sample_daily_sales()
    source["sales"] = source["sales"].astype(float)
    source.loc[source.index[0], "sales"] = -1

    with pytest.raises(ValueError, match="non-negative"):
        build_time_features(source)


def test_feature_builder_rejects_blank_identifiers():
    source = sample_daily_sales()
    source["store"] = source["store"].astype(str)
    source.loc[source.index[0], "store"] = "   "

    with pytest.raises(ValueError, match="nonblank store/item identifiers"):
        build_time_features(source)


def test_feature_builder_rejects_duplicate_calendar_days():
    source = sample_daily_sales()
    duplicate = source.iloc[[0]].copy()
    duplicate["date"] = duplicate["date"] + pd.Timedelta(hours=12)
    source = pd.concat([source, duplicate], ignore_index=True)

    with pytest.raises(ValueError, match="one sales row per date"):
        build_time_features(source)


def test_feature_builder_rejects_irregular_daily_series():
    source = sample_daily_sales().drop(index=5)

    with pytest.raises(ValueError, match="missing or irregular dates"):
        build_time_features(source)


def test_feature_builder_accepts_mixed_date_representations():
    source = sample_daily_sales(days=50)
    source["date"] = [
        date.strftime("%Y-%m-%d") if index % 2 == 0
        else date.strftime("%Y-%m-%d %H:%M:%S")
        for index, date in enumerate(source["date"])
    ]

    features = build_time_features(source)

    assert len(features) == (50 - 14) * 4
    assert features["date"].dt.normalize().nunique() == 36
