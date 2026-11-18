"""Time-series feature engineering and chronological baseline evaluation."""
import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ("date", "store", "item", "sales")


def build_time_features(data: pd.DataFrame) -> pd.DataFrame:
    """Build leakage-safe lag, rolling and calendar features per store-item series.

    Rows are expected to represent one daily observation per store-item pair.
    Rolling features are shifted so the current day's sales never enter its inputs.
    """
    missing = sorted(set(REQUIRED_COLUMNS) - set(data.columns))
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    if data.empty:
        return pd.DataFrame(columns=[
            *REQUIRED_COLUMNS, "lag_1", "lag_7", "lag_14",
            "rolling_mean_7", "rolling_mean_14", "day_of_week", "month",
            "day_of_month", "year",
        ])

    frame = data.loc[:, list(REQUIRED_COLUMNS)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["sales"] = pd.to_numeric(frame["sales"], errors="coerce")
    frame = frame.dropna(subset=["date", "store", "item", "sales"])
    frame = frame.sort_values(["store", "item", "date"]).reset_index(drop=True)
    grouped = frame.groupby(["store", "item"], sort=False)["sales"]

    frame["lag_1"] = grouped.shift(1)
    frame["lag_7"] = grouped.shift(7)
    frame["lag_14"] = grouped.shift(14)
    frame["rolling_mean_7"] = grouped.transform(
        lambda values: values.shift(1).rolling(window=7, min_periods=7).mean()
    )
    frame["rolling_mean_14"] = grouped.transform(
        lambda values: values.shift(1).rolling(window=14, min_periods=14).mean()
    )
    frame["day_of_week"] = frame["date"].dt.day_of_week
    frame["month"] = frame["date"].dt.month
    frame["day_of_month"] = frame["date"].dt.day
    frame["year"] = frame["date"].dt.year
    return frame


def chronological_baseline_backtest(data: pd.DataFrame, holdout_days: int = 28):
    """Compare lag-7 seasonal naive and trailing-7-day mean on the final dates.

    This is a rolling one-step-ahead backtest: each test day's forecast can use
    actual observations from earlier days, but never the current/future day's sales.
    """
    if holdout_days < 1:
        raise ValueError("holdout_days must be at least 1")

    features = build_time_features(data)
    if features.empty:
        raise ValueError("No usable sales rows are available for backtesting.")

    unique_dates = pd.Index(features["date"].dt.normalize().drop_duplicates()).sort_values()
    if len(unique_dates) <= holdout_days:
        raise ValueError("Not enough distinct dates for the requested chronological holdout.")

    test_start = unique_dates[-holdout_days]
    test = features.loc[
        features["date"].dt.normalize().ge(test_start)
        & features["lag_7"].notna()
        & features["rolling_mean_7"].notna()
    ].copy()
    if test.empty:
        raise ValueError("No test rows have sufficient historical data for baseline forecasts.")

    predictions = test[["date", "store", "item", "sales"]].rename(
        columns={"sales": "actual"}
    ).copy()
    predictions["seasonal_naive_7"] = test["lag_7"].to_numpy()
    predictions["moving_average_7"] = test["rolling_mean_7"].to_numpy()

    total_actual = float(predictions["actual"].sum())
    metric_rows = []
    for model_name in ("seasonal_naive_7", "moving_average_7"):
        errors = predictions[model_name] - predictions["actual"]
        mae = float(errors.abs().mean())
        rmse = float(np.sqrt(np.mean(np.square(errors))))
        wape = (
            float(errors.abs().sum() / abs(total_actual) * 100)
            if total_actual != 0 else float("nan")
        )
        bias = (
            float(errors.sum() / total_actual * 100)
            if total_actual != 0 else float("nan")
        )
        metric_rows.append({
            "model": model_name,
            "MAE": mae,
            "RMSE": rmse,
            "WAPE (%)": wape,
            "Bias (%)": bias,
        })

    metrics = pd.DataFrame(metric_rows).sort_values("WAPE (%)").reset_index(drop=True)
    metadata = {
        "holdout_start": pd.Timestamp(test_start).date(),
        "holdout_end": predictions["date"].max().date(),
        "holdout_days_requested": int(holdout_days),
        "test_rows": int(len(predictions)),
        "series_count": int(predictions.groupby(["store", "item"]).ngroups),
    }
    return metrics, predictions, metadata



def evaluate_random_forest(data: pd.DataFrame, holdout_days: int = 28, max_train_rows: int = 200_000):
    """Evaluate a Random Forest on the same chronological holdout as the baselines.

    Training rows are restricted to dates before the holdout. A deterministic
    sample caps training size so the portfolio app remains practical on a laptop.
    Test features use shifted historical observations, so the current target is
    never included in its own prediction inputs.
    """
    if holdout_days < 1:
        raise ValueError("holdout_days must be at least 1")
    if max_train_rows < 1:
        raise ValueError("max_train_rows must be at least 1")

    from sklearn.ensemble import RandomForestRegressor

    features = build_time_features(data)
    if features.empty:
        raise ValueError("No usable sales rows are available for model evaluation.")

    unique_dates = pd.Index(features["date"].dt.normalize().drop_duplicates()).sort_values()
    if len(unique_dates) <= holdout_days:
        raise ValueError("Not enough distinct dates for the requested chronological holdout.")

    test_start = unique_dates[-holdout_days]
    feature_columns = [
        "lag_1", "lag_7", "lag_14", "rolling_mean_7", "rolling_mean_14",
        "day_of_week", "month", "day_of_month", "year",
    ]
    eligible = features.dropna(subset=feature_columns).copy()
    train = eligible.loc[eligible["date"].dt.normalize().lt(test_start)]
    test = eligible.loc[eligible["date"].dt.normalize().ge(test_start)].copy()
    if train.empty or test.empty:
        raise ValueError("Not enough historical rows to train and evaluate the model.")

    if len(train) > max_train_rows:
        train = train.sample(n=max_train_rows, random_state=42)

    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=16,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(train[feature_columns], train["sales"])
    predictions = test[["date", "store", "item", "sales"]].rename(
        columns={"sales": "actual"}
    ).copy()
    predictions["random_forest"] = model.predict(test[feature_columns]).clip(min=0)

    errors = predictions["random_forest"] - predictions["actual"]
    total_actual = float(predictions["actual"].sum())
    metrics = pd.DataFrame([{
        "model": "random_forest",
        "MAE": float(errors.abs().mean()),
        "RMSE": float(np.sqrt(np.mean(np.square(errors)))),
        "WAPE (%)": (
            float(errors.abs().sum() / abs(total_actual) * 100)
            if total_actual != 0 else float("nan")
        ),
        "Bias (%)": (
            float(errors.sum() / total_actual * 100)
            if total_actual != 0 else float("nan")
        ),
    }])
    metadata = {
        "holdout_start": pd.Timestamp(test_start).date(),
        "holdout_end": predictions["date"].max().date(),
        "train_rows_used": int(len(train)),
        "test_rows": int(len(predictions)),
        "series_count": int(predictions.groupby(["store", "item"]).ngroups),
    }
    return metrics, predictions, metadata


def forecast_future_demand(
    data: pd.DataFrame,
    horizon_days: int = 7,
    max_train_rows: int = 200_000,
):
    """Train on all available history and recursively forecast future daily sales.

    The model uses the same leakage-safe lag and rolling features as evaluation.
    Future lag values are populated with earlier model predictions, never future
    actuals. Input must contain one observation per calendar day for each series.
    """
    if horizon_days not in (7, 15, 30):
        raise ValueError("horizon_days must be one of 7, 15 or 30.")
    if max_train_rows < 1:
        raise ValueError("max_train_rows must be at least 1.")

    from sklearn.ensemble import RandomForestRegressor

    features = build_time_features(data)
    if features.empty:
        raise ValueError("No usable sales rows are available for forecasting.")

    frame = data.loc[:, list(REQUIRED_COLUMNS)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["sales"] = pd.to_numeric(frame["sales"], errors="coerce")
    frame = frame.dropna(subset=["date", "store", "item", "sales"])
    if frame.duplicated(["store", "item", "date"]).any():
        raise ValueError(
            "Future forecasting requires one sales row per date, store and item. "
            "Aggregate duplicate daily records before forecasting."
        )

    feature_columns = [
        "lag_1", "lag_7", "lag_14", "rolling_mean_7", "rolling_mean_14",
        "day_of_week", "month", "day_of_month", "year",
    ]
    eligible = features.dropna(subset=feature_columns).copy()
    if eligible.empty:
        raise ValueError("At least 15 daily observations per store-item series are required.")

    histories = {}
    for (store, item), group in frame.groupby(["store", "item"], sort=False):
        group = group.sort_values("date")
        dates = group["date"].reset_index(drop=True)
        if len(dates) < 15:
            raise ValueError(
                f"Store {store}, item {item} has fewer than 15 daily observations."
            )
        if dates.diff().dropna().ne(pd.Timedelta(days=1)).any():
            raise ValueError(
                f"Store {store}, item {item} has missing or irregular dates. "
                "Provide a complete daily series before forecasting."
            )
        histories[(store, item)] = {
            "sales": group["sales"].astype(float).tolist(),
            "last_date": dates.iloc[-1],
        }

    train = eligible
    if len(train) > max_train_rows:
        train = train.sample(n=max_train_rows, random_state=42)

    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=16,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(train[feature_columns], train["sales"])

    forecast_rows = []
    series_keys = list(histories.keys())
    # Predict one horizon step for all series in a single batch. This avoids
    # thousands of tiny model.predict calls on the 500-series Kaggle dataset.
    for step in range(horizon_days):
        feature_rows = []
        forecast_dates = []
        for store, item in series_keys:
            history = histories[(store, item)]
            values = history["sales"]
            current_date = history["last_date"] + pd.Timedelta(days=step + 1)
            forecast_dates.append(current_date)
            feature_rows.append({
                "lag_1": values[-1],
                "lag_7": values[-7],
                "lag_14": values[-14],
                "rolling_mean_7": float(np.mean(values[-7:])),
                "rolling_mean_14": float(np.mean(values[-14:])),
                "day_of_week": current_date.day_of_week,
                "month": current_date.month,
                "day_of_month": current_date.day,
                "year": current_date.year,
            })

        step_features = pd.DataFrame(feature_rows, columns=feature_columns)
        step_predictions = model.predict(step_features).clip(min=0)
        for index, (store, item) in enumerate(series_keys):
            prediction = float(step_predictions[index])
            histories[(store, item)]["sales"].append(prediction)
            forecast_rows.append({
                "date": forecast_dates[index],
                "store": store,
                "item": item,
                "forecast_sales": prediction,
                "forecast_step": step + 1,
            })

    forecast = pd.DataFrame(forecast_rows).sort_values(
        ["date", "store", "item"]
    ).reset_index(drop=True)
    metadata = {
        "horizon_days": int(horizon_days),
        "series_count": int(len(histories)),
        "forecast_rows": int(len(forecast)),
        "training_rows_used": int(len(train)),
        "history_end": frame["date"].max().date(),
        "forecast_start": forecast["date"].min().date(),
        "forecast_end": forecast["date"].max().date(),
    }
    return forecast, metadata


def recursive_multi_horizon_backtest(
    data: pd.DataFrame,
    max_train_rows: int = 200_000,
):
    """Compare recursive forecasts over a shared final 30-day holdout.

    All models forecast the entire holdout without observing its actual sales.
    Metrics are reported for cumulative 7-, 15- and 30-day horizons, matching
    the recursive strategy used by :func:`forecast_future_demand`.
    """
    if max_train_rows < 1:
        raise ValueError("max_train_rows must be at least 1")

    missing = sorted(set(REQUIRED_COLUMNS) - set(data.columns))
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    if data.empty:
        raise ValueError("No sales rows are available for multi-horizon backtesting.")

    frame = data.loc[:, list(REQUIRED_COLUMNS)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["sales"] = pd.to_numeric(frame["sales"], errors="coerce")
    if frame[["date", "store", "item", "sales"]].isna().any().any():
        raise ValueError(
            "Multi-horizon backtesting requires valid dates, store/item identifiers "
            "and numeric sales. Clean invalid rows before evaluation."
        )
    if not np.isfinite(frame["sales"].to_numpy(dtype=float)).all():
        raise ValueError("Sales values must be finite numbers.")
    if frame["sales"].lt(0).any():
        raise ValueError("Sales values must be non-negative.")
    frame["date"] = frame["date"].dt.normalize()

    if frame.duplicated(["store", "item", "date"]).any():
        raise ValueError(
            "Multi-horizon backtesting requires one sales row per date, store and item. "
            "Aggregate duplicate daily records before evaluation."
        )

    frame = frame.sort_values(["store", "item", "date"]).reset_index(drop=True)
    series_groups = list(frame.groupby(["store", "item"], sort=False))
    if not series_groups:
        raise ValueError("No store-item series are available for backtesting.")

    holdout_dates = pd.DatetimeIndex(
        sorted(frame["date"].drop_duplicates())[-30:]
    )
    if len(holdout_dates) < 30:
        raise ValueError("At least 30 distinct dates are required for multi-horizon backtesting.")
    holdout_start = holdout_dates[0]

    histories = {}
    for key, group in series_groups:
        dates = pd.DatetimeIndex(group["date"])
        if len(dates) < 45:
            raise ValueError(
                f"Store {key[0]}, item {key[1]} needs at least 45 daily observations "
                "for a 30-day holdout and 15 days of feature history."
            )
        if dates.diff().dropna().ne(pd.Timedelta(days=1)).any():
            raise ValueError(
                f"Store {key[0]}, item {key[1]} has missing or irregular dates. "
                "Provide a complete daily series before backtesting."
            )
        if not holdout_dates.isin(dates).all():
            raise ValueError(
                "Every store-item series must cover the same final 30-day holdout. "
                "Align the evaluation period before backtesting."
            )
        train_group = group.loc[group["date"].lt(holdout_start)]
        if len(train_group) < 15:
            raise ValueError(
                f"Store {key[0]}, item {key[1]} has insufficient pre-holdout history."
            )
        histories[key] = {
            "sales": train_group["sales"].astype(float).tolist(),
            "actuals": group.loc[group["date"].isin(holdout_dates), "sales"].astype(float).tolist(),
        }

    feature_columns = [
        "lag_1", "lag_7", "lag_14", "rolling_mean_7", "rolling_mean_14",
        "day_of_week", "month", "day_of_month", "year",
    ]
    training_features = build_time_features(frame.loc[frame["date"].lt(holdout_start)])
    training = training_features.dropna(subset=feature_columns).copy()
    if training.empty:
        raise ValueError("Not enough pre-holdout history to train the Random Forest model.")
    if len(training) > max_train_rows:
        training = training.sample(n=max_train_rows, random_state=42)

    from sklearn.ensemble import RandomForestRegressor

    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=16,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(training[feature_columns], training["sales"])

    prediction_rows = []
    series_keys = list(histories)
    for step, forecast_date in enumerate(holdout_dates, start=1):
        rf_features = []
        for key in series_keys:
            values = histories[key]["sales"]
            rf_features.append({
                "lag_1": values[-1],
                "lag_7": values[-7],
                "lag_14": values[-14],
                "rolling_mean_7": float(np.mean(values[-7:])),
                "rolling_mean_14": float(np.mean(values[-14:])),
                "day_of_week": forecast_date.day_of_week,
                "month": forecast_date.month,
                "day_of_month": forecast_date.day,
                "year": forecast_date.year,
            })
        rf_values = model.predict(
            pd.DataFrame(rf_features, columns=feature_columns)
        ).clip(min=0)

        for index, key in enumerate(series_keys):
            history = histories[key]["sales"]
            actual = histories[key]["actuals"][step - 1]
            seasonal_prediction = float(history[-7])
            moving_average_prediction = float(np.mean(history[-7:]))
            rf_prediction = float(rf_values[index])
            for model_name, prediction in (
                ("seasonal_naive_7", seasonal_prediction),
                ("moving_average_7", moving_average_prediction),
                ("random_forest", rf_prediction),
            ):
                prediction_rows.append({
                    "date": forecast_date,
                    "store": key[0],
                    "item": key[1],
                    "actual": actual,
                    "model": model_name,
                    "prediction": prediction,
                    "forecast_step": step,
                })
            # Each model must carry forward its own predictions, not actuals.
            histories[key].setdefault("seasonal_naive_7", []).append(seasonal_prediction)
            histories[key].setdefault("moving_average_7", []).append(moving_average_prediction)
            histories[key].setdefault("random_forest", []).append(rf_prediction)
            # Keep independent histories for the next recursive step.
            if step == 1:
                histories[key]["model_histories"] = {
                    name: list(history) for name, history in (
                        ("seasonal_naive_7", history),
                        ("moving_average_7", history),
                        ("random_forest", history),
                    )
                }
            for model_name, prediction in (
                ("seasonal_naive_7", seasonal_prediction),
                ("moving_average_7", moving_average_prediction),
                ("random_forest", rf_prediction),
            ):
                histories[key]["model_histories"][model_name].append(prediction)

        # The shared base history is not updated with actual holdout sales.
        # Model-specific recursive histories are used below for the next step.
        for key in series_keys:
            histories[key]["sales"] = histories[key]["model_histories"]["random_forest"]

    predictions = pd.DataFrame(prediction_rows)
    metric_rows = []
    for horizon in (7, 15, 30):
        horizon_predictions = predictions.loc[predictions["forecast_step"].le(horizon)]
        for model_name, group in horizon_predictions.groupby("model"):
            errors = group["prediction"] - group["actual"]
            total_actual = float(group["actual"].sum())
            metric_rows.append({
                "model": model_name,
                "horizon_days": horizon,
                "MAE": float(errors.abs().mean()),
                "RMSE": float(np.sqrt(np.mean(np.square(errors)))),
                "WAPE (%)": (
                    float(errors.abs().sum() / abs(total_actual) * 100)
                    if total_actual != 0 else float("nan")
                ),
                "Bias (%)": (
                    float(errors.sum() / total_actual * 100)
                    if total_actual != 0 else float("nan")
                ),
            })

    metrics = pd.DataFrame(metric_rows).sort_values(
        ["horizon_days", "WAPE (%)"]
    ).reset_index(drop=True)
    metadata = {
        "holdout_start": holdout_dates[0].date(),
        "holdout_end": holdout_dates[-1].date(),
        "holdout_days": 30,
        "series_count": int(len(histories)),
        "training_rows_used": int(len(training)),
        "prediction_rows": int(len(predictions)),
        "evaluation_method": "recursive_multi_step",
    }
    return metrics, predictions, metadata
