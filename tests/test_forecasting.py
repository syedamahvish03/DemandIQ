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

    assert len(features) == 50 * 4
    assert features["date"].dt.normalize().nunique() == 50



def test_demand_pattern_diagnostics_classify_smooth_intermittent_erratic_lumpy_and_zero():
    from forecasting import classify_demand_patterns

    dates = pd.date_range("2025-01-01", periods=100, freq="D")
    patterns = {
        "smooth": [10] * 100,
        "intermittent": [10 if index % 3 == 0 else 0 for index in range(100)],
        "erratic": [2 if index % 2 == 0 else 20 for index in range(100)],
        "lumpy": [2 if index % 3 == 0 else 0 for index in range(100)],
        "no_demand": [0] * 100,
    }
    # Use alternating positive sizes for lumpy demand to create high nonzero CV.
    patterns["lumpy"] = [
        (2 if (index // 3) % 2 == 0 else 30) if index % 3 == 0 else 0
        for index in range(100)
    ]
    source = pd.DataFrame([
        {"date": date, "store": 1, "item": item, "sales": sales}
        for item, values in patterns.items()
        for date, sales in zip(dates, values)
    ])

    result = classify_demand_patterns(source).set_index("item")

    assert result.loc["smooth", "demand_pattern"] == "smooth"
    assert result.loc["intermittent", "demand_pattern"] == "intermittent"
    assert result.loc["erratic", "demand_pattern"] == "erratic"
    assert result.loc["lumpy", "demand_pattern"] == "lumpy"
    assert result.loc["no_demand", "demand_pattern"] == "no_demand"
    assert result.loc["intermittent", "zero_demand_days"] > 0
    assert pd.isna(result.loc["no_demand", "ADI"])


def test_demand_pattern_diagnostics_flags_single_nonzero_observation():
    from forecasting import classify_demand_patterns

    dates = pd.date_range("2025-01-01", periods=50, freq="D")
    source = pd.DataFrame({
        "date": dates,
        "store": [1] * 50,
        "item": [101] * 50,
        "sales": [5] + [0] * 49,
    })

    result = classify_demand_patterns(source)

    assert result.loc[0, "demand_pattern"] == "insufficient_nonzero_observations"


def test_weekly_seasonal_naive_repeats_weekday_demand_in_recursive_backtest():
    from forecasting import recursive_multi_horizon_backtest

    dates = pd.date_range("2025-01-01", periods=75, freq="D")
    weekday_demand = [8, 9, 10, 11, 12, 30, 40]
    source = pd.DataFrame({
        "date": dates,
        "store": ["WEEKLY_STORE"] * len(dates),
        "item": ["WEEKLY_ITEM"] * len(dates),
        "sales": [weekday_demand[date.day_of_week] for date in dates],
    })

    metrics, predictions, _ = recursive_multi_horizon_backtest(source)

    seasonal_scores = metrics.loc[
        metrics["model"] == "seasonal_naive_7"
    ].sort_values("horizon_days")
    moving_average_scores = metrics.loc[
        metrics["model"] == "moving_average_7"
    ].sort_values("horizon_days")

    assert seasonal_scores["horizon_days"].tolist() == [7, 15, 30]
    assert seasonal_scores["WAPE (%)"].eq(0).all()
    assert moving_average_scores["WAPE (%)"].gt(0).all()

    seasonal_predictions = predictions.loc[
        predictions["model"] == "seasonal_naive_7"
    ]
    assert seasonal_predictions["prediction"].tolist() == (
        seasonal_predictions["actual"].tolist()
    )


def test_weekday_variation_diagnostic_detects_repeating_weekday_differences():
    from forecasting import measure_weekday_demand_variation

    dates = pd.date_range("2025-01-01", periods=84, freq="D")
    weekday_demand = [10, 10, 10, 10, 10, 30, 40]
    source = pd.DataFrame({
        "date": dates,
        "store": ["WEEKLY_STORE"] * len(dates),
        "item": ["WEEKLY_ITEM"] * len(dates),
        "sales": [weekday_demand[date.day_of_week] for date in dates],
    })

    result = measure_weekday_demand_variation(source).iloc[0]

    assert result["weekday_analysis_status"] == "sufficient_history"
    assert result["minimum_observations_per_weekday"] == 12
    assert result["highest_mean_sales_weekday"] == "Sunday"
    assert result["lowest_mean_sales_weekday"] == "Monday"
    assert result["weekday_mean_dispersion_pct"] > 0


def test_weekday_variation_diagnostic_handles_flat_and_zero_demand():
    from forecasting import measure_weekday_demand_variation

    dates = pd.date_range("2025-01-01", periods=56, freq="D")
    source = pd.DataFrame([
        {
            "date": date,
            "store": 1,
            "item": item,
            "sales": value,
        }
        for item, value in [("flat", 12), ("zero", 0)]
        for date in dates
    ])

    result = measure_weekday_demand_variation(source).set_index("item")

    assert result.loc["flat", "weekday_analysis_status"] == "sufficient_history"
    assert result.loc["flat", "weekday_mean_dispersion_pct"] == pytest.approx(0)
    assert result.loc["zero", "weekday_analysis_status"] == "no_demand"
    assert pd.isna(result.loc["zero", "weekday_mean_dispersion_pct"])


def test_weekday_variation_diagnostic_flags_insufficient_history():
    from forecasting import measure_weekday_demand_variation

    dates = pd.date_range("2025-01-01", periods=20, freq="D")
    source = pd.DataFrame({
        "date": dates,
        "store": [1] * len(dates),
        "item": [101] * len(dates),
        "sales": [10] * len(dates),
    })

    result = measure_weekday_demand_variation(source).iloc[0]

    assert result["weekday_analysis_status"] == "insufficient_weekday_history"
    assert result["minimum_observations_per_weekday"] < 4
    assert pd.isna(result["weekday_mean_dispersion_pct"])


def test_per_series_metrics_report_each_store_item_model_and_horizon():
    from forecasting import per_series_forecast_metrics

    predictions = pd.DataFrame([
        {
            "store": store, "item": item, "model": model,
            "actual": actual, "prediction": prediction, "forecast_step": step,
        }
        for store, item, model, actual, prediction in [
            (1, 101, "model_a", 10.0, 12.0),
            (1, 101, "model_b", 10.0, 10.0),
            (2, 202, "model_a", 20.0, 18.0),
        ]
        for step in range(1, 31)
    ])
    result = per_series_forecast_metrics(predictions)
    row = result.loc[
        (result["store"] == 1) & (result["item"] == 101)
        & (result["model"] == "model_a") & (result["horizon_days"] == 7)
    ].iloc[0]
    assert len(result) == 9
    assert row["evaluation_rows"] == 7
    assert row["MAE"] == pytest.approx(2.0)
    assert row["WAPE (%)"] == pytest.approx(20.0)
    assert row["Bias (%)"] == pytest.approx(20.0)
    assert set(result["horizon_days"]) == {7, 15, 30}


def test_per_series_metrics_marks_zero_actual_wape_and_bias_undefined():
    from forecasting import per_series_forecast_metrics

    predictions = pd.DataFrame({
        "store": [1] * 30, "item": [101] * 30, "model": ["test"] * 30,
        "actual": [0.0] * 30, "prediction": [2.0] * 30,
        "forecast_step": list(range(1, 31)),
    })
    result = per_series_forecast_metrics(predictions)
    assert result["MAE"].eq(2.0).all()
    assert result["WAPE (%)"].isna().all()
    assert result["Bias (%)"].isna().all()


@pytest.mark.parametrize(
    "mutation, message",
    [("duplicate", "one row per store-item-model-forecast-step"),
     ("negative", "non-negative"), ("infinite", "finite")],
)
def test_per_series_metrics_rejects_invalid_prediction_rows(mutation, message):
    from forecasting import per_series_forecast_metrics

    predictions = pd.DataFrame({
        "store": [1, 1], "item": [101, 101], "model": ["test", "test"],
        "actual": [10.0, 10.0], "prediction": [11.0, 11.0],
        "forecast_step": [1, 2],
    })
    if mutation == "duplicate":
        predictions.loc[1, "forecast_step"] = 1
    elif mutation == "negative":
        predictions.loc[0, "actual"] = -1
    else:
        predictions.loc[0, "prediction"] = float("inf")
    with pytest.raises(ValueError, match=message):
        per_series_forecast_metrics(predictions)


def test_per_series_rolling_origin_metrics_report_accuracy_and_origin_stability():
    from forecasting import per_series_rolling_origin_metrics

    predictions = pd.DataFrame([
        {
            "origin": origin, "store": "S1", "item": "P1", "model": "rf",
            "actual": 10.0, "prediction": prediction, "forecast_step": step,
        }
        for origin, prediction in [
            (pd.Timestamp("2025-01-01"), 12.0),
            (pd.Timestamp("2025-01-16"), 8.0),
        ]
        for step in range(1, 31)
    ])
    result = per_series_rolling_origin_metrics(predictions)

    assert result["horizon_days"].tolist() == [7, 15, 30]
    row = result.loc[result["horizon_days"] == 7].iloc[0]
    assert row["origins_evaluated"] == 2
    assert row["evaluation_rows"] == 14
    assert row["WAPE (%)"] == pytest.approx(20.0)
    assert row["Bias (%)"] == pytest.approx(0.0)
    assert row["mean_origin_WAPE (%)"] == pytest.approx(20.0)
    assert row["WAPE_std_across_origins (%)"] == pytest.approx(0.0)


def test_per_series_rolling_origin_metrics_marks_zero_demand_percentage_metrics_undefined():
    from forecasting import per_series_rolling_origin_metrics

    predictions = pd.DataFrame([
        {
            "origin": origin, "store": 1, "item": 2, "model": "rf",
            "actual": 0.0, "prediction": 3.0, "forecast_step": step,
        }
        for origin in ("origin_a", "origin_b")
        for step in range(1, 31)
    ])
    result = per_series_rolling_origin_metrics(predictions)

    assert result["MAE"].eq(3.0).all()
    assert result["WAPE (%)"].isna().all()
    assert result["Bias (%)"].isna().all()
    assert result["mean_origin_WAPE (%)"].isna().all()
    assert result["WAPE_std_across_origins (%)"].isna().all()


def test_per_series_rolling_origin_metrics_rejects_duplicate_origin_steps():
    from forecasting import per_series_rolling_origin_metrics

    predictions = pd.DataFrame({
        "origin": ["origin_a", "origin_a"],
        "store": [1, 1], "item": [2, 2], "model": ["rf", "rf"],
        "actual": [10.0, 10.0], "prediction": [11.0, 11.0],
        "forecast_step": [1, 1],
    })
    with pytest.raises(ValueError, match="one row per origin-store-item-model-forecast-step"):
        per_series_rolling_origin_metrics(predictions)



def test_per_series_model_recommendations_rank_by_mean_origin_wape_and_stability():
    from forecasting import recommend_per_series_models

    metrics = pd.DataFrame([
        {
            "store": 1, "item": 101, "model": model, "horizon_days": 7,
            "origins_evaluated": 3, "evaluation_rows": 21,
            "WAPE (%)": pooled, "mean_origin_WAPE (%)": mean_wape,
            "WAPE_std_across_origins (%)": std_wape, "actual_units": 210,
        }
        for model, pooled, mean_wape, std_wape in [
            ("random_forest", 11.0, 10.0, 2.0),
            ("seasonal_naive_7", 10.5, 10.0, 1.0),
            ("moving_average_7", 13.0, 13.0, 3.0),
        ]
    ])

    result = recommend_per_series_models(metrics).iloc[0]

    assert result["recommended_model"] == "seasonal_naive_7"
    assert result["runner_up_model"] == "random_forest"
    assert result["mean_origin_WAPE (%)"] == pytest.approx(10.0)
    assert result["WAPE_std_across_origins (%)"] == pytest.approx(1.0)
    assert result["WAPE_gap_vs_runner_up (pp)"] == pytest.approx(0.0)
    assert result["models_ranked"] == 3
    assert result["selection_status"] == "recommended_by_mean_origin_wape"


def test_per_series_model_recommendations_handles_zero_demand_without_ranking():
    from forecasting import recommend_per_series_models

    metrics = pd.DataFrame([
        {
            "store": 1, "item": 101, "model": model, "horizon_days": 30,
            "origins_evaluated": 3, "evaluation_rows": 90,
            "WAPE (%)": float("nan"), "mean_origin_WAPE (%)": float("nan"),
            "WAPE_std_across_origins (%)": float("nan"), "actual_units": 0,
        }
        for model in ("random_forest", "seasonal_naive_7")
    ])

    result = recommend_per_series_models(metrics).iloc[0]

    assert result["recommended_model"] is None
    assert result["runner_up_model"] is None
    assert result["models_ranked"] == 0
    assert result["selection_status"] == "no_positive_demand_for_wape_ranking"
    assert pd.isna(result["mean_origin_WAPE (%)"])


@pytest.mark.parametrize(
    "mutation, message",
    [
        ("duplicate", "one row per store-item-model-horizon"),
        ("negative", "cannot be negative"),
        ("invalid_horizon", "horizons must be 7, 15 or 30"),
    ],
)
def test_per_series_model_recommendations_rejects_invalid_metrics(mutation, message):
    from forecasting import recommend_per_series_models

    metrics = pd.DataFrame([
        {
            "store": 1, "item": 101, "model": "random_forest",
            "horizon_days": 7, "origins_evaluated": 3, "evaluation_rows": 21,
            "WAPE (%)": 10.0, "mean_origin_WAPE (%)": 11.0,
            "WAPE_std_across_origins (%)": 1.0, "actual_units": 210,
        }
    ])
    if mutation == "duplicate":
        metrics = pd.concat([metrics, metrics], ignore_index=True)
    elif mutation == "negative":
        metrics.loc[0, "mean_origin_WAPE (%)"] = -1
    else:
        metrics.loc[0, "horizon_days"] = 10

    with pytest.raises(ValueError, match=message):
        recommend_per_series_models(metrics)



def test_forecast_error_by_step_reports_recursive_error_growth():
    from forecasting import forecast_error_by_step

    predictions = pd.DataFrame([
        {
            "store": store, "item": item, "model": "random_forest",
            "actual": 10.0, "prediction": 10.0 + step,
            "forecast_step": step,
        }
        for step in range(1, 4)
        for store, item in [(1, 101), (2, 102)]
    ])

    result = forecast_error_by_step(predictions)

    assert result["forecast_step"].tolist() == [1, 2, 3]
    assert result["evaluation_rows"].tolist() == [2, 2, 2]
    assert result["MAE"].tolist() == pytest.approx([1.0, 2.0, 3.0])
    assert result["WAPE (%)"].tolist() == pytest.approx([10.0, 20.0, 30.0])
    assert result["Bias (%)"].tolist() == pytest.approx([10.0, 20.0, 30.0])


def test_forecast_error_by_step_marks_zero_demand_percentage_metrics_undefined():
    from forecasting import forecast_error_by_step

    predictions = pd.DataFrame({
        "store": [1, 1], "item": [101, 101], "model": ["rf", "rf"],
        "actual": [0.0, 0.0], "prediction": [2.0, 4.0],
        "forecast_step": [1, 2],
    })

    result = forecast_error_by_step(predictions)

    assert result["MAE"].tolist() == [2.0, 4.0]
    assert result["WAPE (%)"].isna().all()
    assert result["Bias (%)"].isna().all()


@pytest.mark.parametrize(
    "mutation, message",
    [
        ("duplicate", "one row per store-item-model-forecast-step"),
        ("negative", "non-negative"),
        ("invalid_step", "positive whole numbers"),
    ],
)
def test_forecast_error_by_step_rejects_invalid_prediction_rows(mutation, message):
    from forecasting import forecast_error_by_step

    predictions = pd.DataFrame({
        "store": [1], "item": [101], "model": ["rf"],
        "actual": [10.0], "prediction": [11.0], "forecast_step": [1],
    })
    if mutation == "duplicate":
        predictions = pd.concat([predictions, predictions], ignore_index=True)
    elif mutation == "negative":
        predictions.loc[0, "actual"] = -1
    else:
        predictions.loc[0, "forecast_step"] = 0

    with pytest.raises(ValueError, match=message):
        forecast_error_by_step(predictions)

def _pattern_evaluation_fixture():
    from forecasting import forecast_accuracy_by_demand_pattern

    dates = pd.date_range("2025-01-01", periods=60, freq="D")
    history_rows = []
    prediction_rows = []
    origin = dates[-1] + pd.Timedelta(days=1)
    for item, pattern_sales in (
        (101, lambda index: 10.0),
        (102, lambda index: 10.0 if index % 5 == 0 else 0.0),
    ):
        for index, date in enumerate(dates):
            history_rows.append({
                "date": date, "store": 1, "item": item,
                "sales": pattern_sales(index),
            })
        for step in range(1, 31):
            prediction_rows.append({
                "date": origin + pd.Timedelta(days=step),
                "store": 1, "item": item, "model": "random_forest",
                "actual": 12.0 if item == 101 else (10.0 if step % 5 == 0 else 0.0),
                "prediction": 11.0 if item == 101 else 1.0,
                "forecast_step": step,
            })
    return pd.DataFrame(history_rows), pd.DataFrame(prediction_rows)


def test_demand_pattern_forecast_metrics_segment_by_pre_origin_pattern_and_horizon():
    from forecasting import forecast_accuracy_by_demand_pattern

    history, predictions = _pattern_evaluation_fixture()
    metrics = forecast_accuracy_by_demand_pattern(predictions, history)

    assert set(metrics["demand_pattern"]) == {"smooth", "intermittent"}
    assert set(metrics["horizon_days"]) == {7, 15, 30}
    assert metrics.groupby("demand_pattern")["horizon_days"].nunique().eq(3).all()
    intermittent_7 = metrics.loc[
        (metrics["demand_pattern"] == "intermittent")
        & metrics["horizon_days"].eq(7)
    ].iloc[0]
    assert intermittent_7["evaluation_rows"] == 7
    assert intermittent_7["series_count"] == 1


def test_demand_pattern_forecast_metrics_do_not_use_post_origin_history():
    from forecasting import forecast_accuracy_by_demand_pattern

    history, predictions = _pattern_evaluation_fixture()
    original = forecast_accuracy_by_demand_pattern(predictions, history)
    future_rows = []
    origin = predictions["date"].min() - pd.Timedelta(days=1)
    for item in (101, 102):
        for step in range(1, 31):
            future_rows.append({
                "date": origin + pd.Timedelta(days=step),
                "store": 1, "item": item, "sales": 9999.0,
            })
    extended_history = pd.concat(
        [history, pd.DataFrame(future_rows)], ignore_index=True
    )
    extended = forecast_accuracy_by_demand_pattern(predictions, extended_history)

    assert original[["demand_pattern", "model", "horizon_days"]].equals(
        extended[["demand_pattern", "model", "horizon_days"]]
    )


def test_demand_pattern_forecast_metrics_reject_mixed_forecast_origins():
    from forecasting import forecast_accuracy_by_demand_pattern

    history, predictions = _pattern_evaluation_fixture()
    predictions.loc[predictions.index[0], "date"] += pd.Timedelta(days=1)

    with pytest.raises(ValueError, match="one common forecast origin"):
        forecast_accuracy_by_demand_pattern(predictions, history)



def test_empirical_error_bands_by_step_calculates_signed_residual_quantiles():
    from forecasting import empirical_error_bands_by_step

    rows = []
    errors = [-10, -5, -2, -1, 0, 1, 2, 5, 10, 12]
    for index, error in enumerate(errors):
        rows.append({
            "origin": f"origin-{index}",
            "store": 1,
            "item": 101,
            "model": "random_forest",
            "actual": 100 + error,
            "prediction": 100,
            "forecast_step": 1,
        })
    result = empirical_error_bands_by_step(
        pd.DataFrame(rows), lower_quantile=0.1, upper_quantile=0.9, min_samples=10
    )
    assert result.loc[0, "sample_count"] == 10
    assert result.loc[0, "lower_error_bound"] == pytest.approx(-5.5)
    assert result.loc[0, "upper_error_bound"] == pytest.approx(10.2)
    assert result.loc[0, "calibration_status"] == "sufficient_history"


def test_empirical_error_bands_by_step_flags_insufficient_samples():
    from forecasting import empirical_error_bands_by_step

    predictions = pd.DataFrame([{
        "origin": "2025-01-01", "store": 1, "item": 101,
        "model": "random_forest", "actual": 10, "prediction": 8,
        "forecast_step": 1,
    }])
    result = empirical_error_bands_by_step(predictions, min_samples=20)
    assert result.loc[0, "calibration_status"] == "insufficient_history"
    assert pd.isna(result.loc[0, "lower_error_bound"])
    assert pd.isna(result.loc[0, "upper_error_bound"])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"lower_quantile": 0.95, "upper_quantile": 0.05},
        {"lower_quantile": -0.1, "upper_quantile": 0.95},
        {"min_samples": 0},
    ],
)
def test_empirical_error_bands_by_step_rejects_invalid_configuration(kwargs):
    from forecasting import empirical_error_bands_by_step

    predictions = pd.DataFrame([{
        "origin": "2025-01-01", "store": 1, "item": 101,
        "model": "random_forest", "actual": 10, "prediction": 8,
        "forecast_step": 1,
    }])
    with pytest.raises(ValueError):
        empirical_error_bands_by_step(predictions, **kwargs)
