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
    for column in ("store", "item"):
        frame[column] = frame[column].map(
            lambda value: value.strip() if isinstance(value, str) else value
        )
    frame["date"] = pd.to_datetime(frame["date"], format="mixed", errors="coerce")
    frame["sales"] = pd.to_numeric(frame["sales"], errors="coerce")

    blank_identifiers = frame[["store", "item"]].apply(
        lambda column: column.map(
            lambda value: isinstance(value, str) and not value
        )
    )
    if (
        frame[["date", "store", "item", "sales"]].isna().any().any()
        or blank_identifiers.any(axis=1).any()
    ):
        raise ValueError(
            "Forecasting requires valid dates, nonblank store/item identifiers "
            "and numeric sales. Clean invalid rows before feature engineering."
        )
    if not np.isfinite(frame["sales"].to_numpy(dtype=float)).all():
        raise ValueError("Sales values must be finite numbers.")
    if frame["sales"].lt(0).any():
        raise ValueError("Sales values must be non-negative.")

    frame["date"] = frame["date"].dt.normalize()
    if frame.duplicated(["store", "item", "date"]).any():
        raise ValueError(
            "Forecasting requires one sales row per date, store and item. "
            "Aggregate duplicate daily records before feature engineering."
        )

    frame = frame.sort_values(["store", "item", "date"]).reset_index(drop=True)
    for (store, item), group in frame.groupby(["store", "item"], sort=False):
        dates = pd.DatetimeIndex(group["date"])
        if (dates[1:] - dates[:-1] != pd.Timedelta(days=1)).any():
            raise ValueError(
                f"Store {store}, item {item} has missing or irregular dates. "
                "Provide a complete daily series before feature engineering."
            )

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



def classify_demand_patterns(data: pd.DataFrame) -> pd.DataFrame:
    """Classify each daily store-item series using ADI and squared CV.

    Uses the conventional ADI=1.32 and CV-squared=0.49 boundaries for
    smooth, intermittent, erratic and lumpy demand. Series with no positive
    demand or fewer than two positive observations are reported separately;
    this diagnostic does not alter model forecasts or inventory calculations.
    """
    features = build_time_features(data)
    if features.empty:
        raise ValueError("No usable sales rows are available for demand-pattern analysis.")

    rows = []
    for (store, item), group in features.groupby(["store", "item"], sort=False):
        values = group["sales"].astype(float)
        positive = values.loc[values.gt(0)]
        nonzero_days = int(len(positive))
        observations = int(len(values))
        adi = float(observations / nonzero_days) if nonzero_days else float("nan")
        cv_squared = float("nan")
        if nonzero_days == 0:
            pattern = "no_demand"
        elif nonzero_days < 2:
            pattern = "insufficient_nonzero_observations"
        else:
            mean_positive = float(positive.mean())
            cv_squared = float((positive.std(ddof=1) / mean_positive) ** 2)
            if adi < 1.32:
                pattern = "smooth" if cv_squared < 0.49 else "erratic"
            else:
                pattern = "intermittent" if cv_squared < 0.49 else "lumpy"

        rows.append({
            "store": store,
            "item": item,
            "observations": observations,
            "nonzero_demand_days": nonzero_days,
            "zero_demand_days": observations - nonzero_days,
            "ADI": adi,
            "CV_squared": cv_squared,
            "demand_pattern": pattern,
        })

    return pd.DataFrame(rows).sort_values(
        ["demand_pattern", "store", "item"]
    ).reset_index(drop=True)


def measure_weekday_demand_variation(data: pd.DataFrame) -> pd.DataFrame:
    """Measure descriptive variation in mean sales across weekdays per series.

    At least four observations for every weekday are required. The dispersion
    metric is not a statistical seasonality test and can also reflect trends,
    promotions, holidays or other calendar effects. It does not alter forecasts.
    """
    features = build_time_features(data)
    if features.empty:
        raise ValueError("No usable sales rows are available for weekday analysis.")

    rows = []
    for (store, item), group in features.groupby(["store", "item"], sort=False):
        weekday = group.assign(weekday=group["date"].dt.day_of_week)
        weekday_stats = weekday.groupby("weekday")["sales"].agg(["mean", "count"])
        counts = weekday_stats["count"].reindex(range(7), fill_value=0)
        means = weekday_stats["mean"].reindex(range(7))
        sufficient_history = bool(counts.ge(4).all())
        overall_mean = float(group["sales"].mean())
        dispersion = float("nan")
        strongest = None
        weakest = None
        if sufficient_history and overall_mean > 0:
            weekday_means = means.astype(float)
            dispersion = float(
                weekday_means.std(ddof=0) / weekday_means.mean() * 100
            )
            strongest = pd.Timestamp("2025-01-06") + pd.Timedelta(
                days=int(weekday_means.idxmax())
            )
            weakest = pd.Timestamp("2025-01-06") + pd.Timedelta(
                days=int(weekday_means.idxmin())
            )

        rows.append({
            "store": store,
            "item": item,
            "observations": int(len(group)),
            "minimum_observations_per_weekday": int(counts.min()),
            "weekday_mean_dispersion_pct": dispersion,
            "highest_mean_sales_weekday": strongest.day_name() if strongest is not None else None,
            "lowest_mean_sales_weekday": weakest.day_name() if weakest is not None else None,
            "weekday_analysis_status": (
                "no_demand" if overall_mean == 0
                else "sufficient_history" if sufficient_history
                else "insufficient_weekday_history"
            ),
        })

    return pd.DataFrame(rows).sort_values(
        ["weekday_analysis_status", "store", "item"]
    ).reset_index(drop=True)

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
    frame["date"] = pd.to_datetime(frame["date"], format="mixed", errors="coerce").dt.normalize()
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
    frame["date"] = pd.to_datetime(frame["date"], format="mixed", errors="coerce")
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
        raise ValueError("at least 30 distinct dates are required for multi-horizon backtesting.")
    holdout_start = holdout_dates[0]

    model_names = ("seasonal_naive_7", "moving_average_7", "random_forest")
    histories = {}
    for key, group in series_groups:
        dates = pd.DatetimeIndex(group["date"])
        if len(dates) < 45:
            raise ValueError(
                f"Store {key[0]}, item {key[1]} needs at least 45 daily observations "
                "for a 30-day holdout and 15 days of feature history."
            )
        if (dates.diff().dropna() != pd.Timedelta(days=1)).any():
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
        initial_history = train_group["sales"].astype(float).tolist()
        histories[key] = {
            "actuals": group.loc[
                group["date"].isin(holdout_dates), "sales"
            ].astype(float).tolist(),
            "model_histories": {
                model_name: list(initial_history) for model_name in model_names
            },
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
            values = histories[key]["model_histories"]["random_forest"]
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
            series = histories[key]
            seasonal_history = series["model_histories"]["seasonal_naive_7"]
            average_history = series["model_histories"]["moving_average_7"]
            rf_history = series["model_histories"]["random_forest"]
            step_predictions = {
                "seasonal_naive_7": float(seasonal_history[-7]),
                "moving_average_7": float(np.mean(average_history[-7:])),
                "random_forest": float(rf_values[index]),
            }
            actual = series["actuals"][step - 1]
            for model_name, prediction in step_predictions.items():
                prediction_rows.append({
                    "date": forecast_date,
                    "store": key[0],
                    "item": key[1],
                    "actual": actual,
                    "model": model_name,
                    "prediction": prediction,
                    "forecast_step": step,
                })
                series["model_histories"][model_name].append(prediction)

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



def per_series_forecast_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    """Calculate recursive errors per store-item, model and cumulative horizon."""
    required = {"store", "item", "model", "actual", "prediction", "forecast_step"}
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise ValueError("Missing required prediction columns: " + ", ".join(missing))
    if predictions.empty:
        raise ValueError("No prediction rows are available for per-series evaluation.")
    frame = predictions.loc[:, list(required)].copy()
    for column in ("actual", "prediction", "forecast_step"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[list(required)].isna().any().any():
        raise ValueError("Per-series evaluation requires valid identifiers and numeric predictions.")
    values = frame[["actual", "prediction", "forecast_step"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Per-series evaluation values must be finite.")
    if frame["actual"].lt(0).any() or frame["prediction"].lt(0).any():
        raise ValueError("Actual and predicted demand must be non-negative.")
    steps = frame["forecast_step"]
    if steps.lt(1).any() or not steps.mod(1).eq(0).all():
        raise ValueError("Forecast steps must be positive whole numbers.")
    if frame.duplicated(["store", "item", "model", "forecast_step"]).any():
        raise ValueError("Predictions must contain one row per store-item-model-forecast-step.")
    rows = []
    for (store, item, model_name), group in frame.groupby(["store", "item", "model"], sort=False):
        for horizon in (7, 15, 30):
            window = group.loc[group["forecast_step"].le(horizon)]
            if window.empty:
                continue
            errors = window["prediction"] - window["actual"]
            total_actual = float(window["actual"].sum())
            rows.append({
                "store": store, "item": item, "model": model_name,
                "horizon_days": horizon, "evaluation_rows": int(len(window)),
                "MAE": float(errors.abs().mean()),
                "RMSE": float(np.sqrt(np.mean(np.square(errors)))),
                "WAPE (%)": float(errors.abs().sum() / total_actual * 100) if total_actual > 0 else float("nan"),
                "Bias (%)": float(errors.sum() / total_actual * 100) if total_actual > 0 else float("nan"),
                "actual_units": total_actual,
            })
    return pd.DataFrame(rows).sort_values(["horizon_days", "model", "store", "item"]).reset_index(drop=True)


def forecast_accuracy_by_demand_pattern(
    predictions: pd.DataFrame,
    historical_data: pd.DataFrame,
) -> pd.DataFrame:
    """Break recursive holdout accuracy down by demand pattern known at forecast origin.

    Demand patterns are classified using historical rows strictly before the
    common forecast origin. Holdout actuals are never used to assign a pattern.
    """
    required_predictions = {
        "date", "store", "item", "model", "actual", "prediction", "forecast_step"
    }
    missing = sorted(required_predictions - set(predictions.columns))
    if missing:
        raise ValueError("Missing required prediction columns: " + ", ".join(missing))
    missing_history = sorted(set(REQUIRED_COLUMNS) - set(historical_data.columns))
    if missing_history:
        raise ValueError("Historical data is missing required columns: " + ", ".join(missing_history))
    if predictions.empty:
        raise ValueError("No prediction rows are available for demand-pattern evaluation.")

    frame = predictions.loc[:, list(required_predictions)].copy()
    frame["date"] = pd.to_datetime(frame["date"], format="mixed", errors="coerce").dt.normalize()
    for column in ("actual", "prediction", "forecast_step"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[list(required_predictions)].isna().any().any():
        raise ValueError("Demand-pattern evaluation requires valid dates, identifiers and numeric predictions.")
    values = frame[["actual", "prediction", "forecast_step"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Demand-pattern evaluation values must be finite.")
    if frame["actual"].lt(0).any() or frame["prediction"].lt(0).any():
        raise ValueError("Actual and predicted demand must be non-negative.")
    if frame["forecast_step"].lt(1).any() or not frame["forecast_step"].mod(1).eq(0).all():
        raise ValueError("Forecast steps must be positive whole numbers.")
    if frame[["store", "item", "model"]].astype(str).apply(
        lambda column: column.str.strip().eq("")
    ).any(axis=1).any():
        raise ValueError("Store, item and model identifiers must be nonblank.")
    if frame.duplicated(["date", "store", "item", "model"]).any():
        raise ValueError("Demand-pattern evaluation requires one row per date-store-item-model.")

    origin_dates = (
        frame["date"] - pd.to_timedelta(frame["forecast_step"], unit="D")
    ).drop_duplicates()
    if len(origin_dates) != 1:
        raise ValueError("Demand-pattern evaluation requires predictions from one common forecast origin.")
    origin = origin_dates.iloc[0]

    history = historical_data.loc[:, list(REQUIRED_COLUMNS)].copy()
    history["date"] = pd.to_datetime(history["date"], format="mixed", errors="coerce").dt.normalize()
    history = history.loc[history["date"].lt(origin)].copy()
    if history.empty:
        raise ValueError("No pre-origin historical data is available for demand-pattern classification.")

    patterns = classify_demand_patterns(history)
    pattern_lookup = {
        (row.store, row.item): row.demand_pattern
        for row in patterns.itertuples(index=False)
    }
    frame["demand_pattern"] = [
        pattern_lookup.get((store, item))
        for store, item in zip(frame["store"], frame["item"])
    ]
    if frame["demand_pattern"].isna().any():
        raise ValueError("Every forecast store-item pair must have pre-origin demand history.")

    rows = []
    for (pattern, model_name), series in frame.groupby(
        ["demand_pattern", "model"], sort=True
    ):
        for horizon in (7, 15, 30):
            window = series.loc[series["forecast_step"].le(horizon)]
            if window.empty:
                continue
            errors = window["prediction"] - window["actual"]
            actual_units = float(window["actual"].sum())
            rows.append({
                "demand_pattern": pattern,
                "model": model_name,
                "horizon_days": horizon,
                "series_count": int(window[["store", "item"]].drop_duplicates().shape[0]),
                "evaluation_rows": int(len(window)),
                "MAE": float(errors.abs().mean()),
                "RMSE": float(np.sqrt(np.mean(np.square(errors)))),
                "WAPE (%)": float(errors.abs().sum() / actual_units * 100)
                    if actual_units > 0 else float("nan"),
                "Bias (%)": float(errors.sum() / actual_units * 100)
                    if actual_units > 0 else float("nan"),
                "actual_units": actual_units,
            })
    return pd.DataFrame(rows).sort_values(
        ["horizon_days", "demand_pattern", "model"]
    ).reset_index(drop=True)


def forecast_error_by_step(predictions: pd.DataFrame) -> pd.DataFrame:
    """Measure recursive forecast accuracy separately at each forecast lead day."""
    required = {"store", "item", "model", "actual", "prediction", "forecast_step"}
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise ValueError("Missing required prediction columns: " + ", ".join(missing))
    if predictions.empty:
        raise ValueError("No prediction rows are available for forecast-step analysis.")

    frame = predictions.loc[:, list(required)].copy()
    for column in ("actual", "prediction", "forecast_step"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[list(required)].isna().any().any():
        raise ValueError("Forecast-step analysis requires valid identifiers and numeric predictions.")
    values = frame[["actual", "prediction", "forecast_step"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Forecast-step analysis values must be finite.")
    if frame["actual"].lt(0).any() or frame["prediction"].lt(0).any():
        raise ValueError("Actual and predicted demand must be non-negative.")
    if frame["forecast_step"].lt(1).any() or not frame["forecast_step"].mod(1).eq(0).all():
        raise ValueError("Forecast steps must be positive whole numbers.")
    if frame.duplicated(["store", "item", "model", "forecast_step"]).any():
        raise ValueError("Forecast-step analysis requires one row per store-item-model-forecast-step.")

    rows = []
    for (model_name, step), group in frame.groupby(["model", "forecast_step"], sort=True):
        errors = group["prediction"] - group["actual"]
        actual_units = float(group["actual"].sum())
        rows.append({
            "model": model_name,
            "forecast_step": int(step),
            "evaluation_rows": int(len(group)),
            "MAE": float(errors.abs().mean()),
            "RMSE": float(np.sqrt(np.mean(np.square(errors)))),
            "WAPE (%)": (
                float(errors.abs().sum() / actual_units * 100)
                if actual_units > 0 else float("nan")
            ),
            "Bias (%)": (
                float(errors.sum() / actual_units * 100)
                if actual_units > 0 else float("nan")
            ),
            "actual_units": actual_units,
        })

    return pd.DataFrame(rows).sort_values(
        ["model", "forecast_step"]
    ).reset_index(drop=True)


def per_series_rolling_origin_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    """Summarize recursive forecast accuracy and origin stability per store-item."""
    required = {
        "origin", "store", "item", "model", "actual", "prediction", "forecast_step"
    }
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise ValueError("Missing required rolling prediction columns: " + ", ".join(missing))
    if predictions.empty:
        raise ValueError("No rolling-origin prediction rows are available.")
    frame = predictions.loc[:, list(required)].copy()
    for column in ("actual", "prediction", "forecast_step"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[list(required)].isna().any().any():
        raise ValueError("Rolling-origin evaluation requires valid origins, identifiers and numeric predictions.")
    values = frame[["actual", "prediction", "forecast_step"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Rolling-origin evaluation values must be finite.")
    if frame["actual"].lt(0).any() or frame["prediction"].lt(0).any():
        raise ValueError("Actual and predicted demand must be non-negative.")
    steps = frame["forecast_step"]
    if steps.lt(1).any() or not steps.mod(1).eq(0).all():
        raise ValueError("Forecast steps must be positive whole numbers.")
    key_columns = ["origin", "store", "item", "model", "forecast_step"]
    if frame.duplicated(key_columns).any():
        raise ValueError(
            "Rolling predictions must contain one row per origin-store-item-model-forecast-step."
        )

    rows = []
    series_columns = ["store", "item", "model"]
    for (store, item, model_name), series in frame.groupby(series_columns, sort=False):
        for horizon in (7, 15, 30):
            window = series.loc[series["forecast_step"].le(horizon)]
            if window.empty:
                continue
            errors = window["prediction"] - window["actual"]
            total_actual = float(window["actual"].sum())
            origin_wapes = []
            for _, origin_group in window.groupby("origin", sort=False):
                origin_actual = float(origin_group["actual"].sum())
                if origin_actual > 0:
                    origin_wapes.append(
                        float((origin_group["prediction"] - origin_group["actual"]).abs().sum()
                              / origin_actual * 100)
                    )
            rows.append({
                "store": store,
                "item": item,
                "model": model_name,
                "horizon_days": horizon,
                "origins_evaluated": int(window["origin"].nunique()),
                "evaluation_rows": int(len(window)),
                "MAE": float(errors.abs().mean()),
                "RMSE": float(np.sqrt(np.mean(np.square(errors)))),
                "WAPE (%)": float(errors.abs().sum() / total_actual * 100)
                    if total_actual > 0 else float("nan"),
                "Bias (%)": float(errors.sum() / total_actual * 100)
                    if total_actual > 0 else float("nan"),
                "mean_origin_WAPE (%)": float(np.mean(origin_wapes))
                    if origin_wapes else float("nan"),
                "WAPE_std_across_origins (%)": float(np.std(origin_wapes, ddof=0))
                    if origin_wapes else float("nan"),
                "actual_units": total_actual,
            })
    return pd.DataFrame(rows).sort_values(
        ["horizon_days", "model", "store", "item"]
    ).reset_index(drop=True)


def recommend_per_series_models(metrics: pd.DataFrame) -> pd.DataFrame:
    """Rank candidate models per store-item and horizon using rolling-origin WAPE.

    Ranking uses mean origin-level WAPE, with lower cross-origin WAPE standard
    deviation as the tie-breaker. This is evaluation guidance only; it does not
    change the production forecasting model.
    """
    required = {
        "store", "item", "model", "horizon_days", "origins_evaluated",
        "evaluation_rows", "WAPE (%)", "mean_origin_WAPE (%)",
        "WAPE_std_across_origins (%)", "actual_units",
    }
    missing = sorted(required - set(metrics.columns))
    if missing:
        raise ValueError("Missing model-selection metric columns: " + ", ".join(missing))
    if metrics.empty:
        raise ValueError("No per-series rolling-origin metrics are available.")

    frame = metrics.loc[:, list(required)].copy()
    nullable = {"WAPE (%)", "mean_origin_WAPE (%)", "WAPE_std_across_origins (%)"}
    required_nonnull = list(required - nullable)
    if frame[required_nonnull].isna().any().any():
        raise ValueError("Model-selection metrics require valid identifiers and counts.")
    for column in (
        "horizon_days", "origins_evaluated", "evaluation_rows",
        "WAPE (%)", "mean_origin_WAPE (%)",
        "WAPE_std_across_origins (%)", "actual_units",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    numeric_columns = [
        "horizon_days", "origins_evaluated", "evaluation_rows",
        "WAPE (%)", "mean_origin_WAPE (%)",
        "WAPE_std_across_origins (%)", "actual_units",
    ]
    for column in numeric_columns:
        values = frame[column].dropna().to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("Model-selection metrics must contain finite numeric values.")
    if not frame["horizon_days"].isin((7, 15, 30)).all():
        raise ValueError("Model-selection horizons must be 7, 15 or 30 days.")
    if (
        frame["origins_evaluated"].lt(1).any()
        or not frame["origins_evaluated"].mod(1).eq(0).all()
        or frame["evaluation_rows"].lt(1).any()
        or not frame["evaluation_rows"].mod(1).eq(0).all()
    ):
        raise ValueError("Model-selection origin and evaluation counts must be positive whole numbers.")
    for column in ("WAPE (%)", "mean_origin_WAPE (%)", "WAPE_std_across_origins (%)"):
        if frame[column].dropna().lt(0).any():
            raise ValueError("Model-selection percentage-error metrics cannot be negative.")
    if frame["actual_units"].lt(0).any():
        raise ValueError("Model-selection actual demand cannot be negative.")
    key_columns = ["store", "item", "model", "horizon_days"]
    if frame.duplicated(key_columns).any():
        raise ValueError("Model-selection metrics must contain one row per store-item-model-horizon.")

    rows = []
    for (store, item, horizon), group in frame.groupby(
        ["store", "item", "horizon_days"], sort=False
    ):
        ranked = group.dropna(subset=["mean_origin_WAPE (%)"]).sort_values(
            ["mean_origin_WAPE (%)", "WAPE_std_across_origins (%)", "model"],
            na_position="last",
        )
        if ranked.empty:
            rows.append({
                "store": store,
                "item": item,
                "horizon_days": int(horizon),
                "models_evaluated": int(len(group)),
                "models_ranked": 0,
                "recommended_model": None,
                "runner_up_model": None,
                "mean_origin_WAPE (%)": float("nan"),
                "WAPE_std_across_origins (%)": float("nan"),
                "runner_up_mean_origin_WAPE (%)": float("nan"),
                "WAPE_gap_vs_runner_up (pp)": float("nan"),
                "pooled_WAPE (%)": float("nan"),
                "origins_evaluated": int(group["origins_evaluated"].max()),
                "evaluation_rows": int(group["evaluation_rows"].max()),
                "actual_units": float(group["actual_units"].max()),
                "selection_status": "no_positive_demand_for_wape_ranking",
            })
            continue

        best = ranked.iloc[0]
        runner_up = ranked.iloc[1] if len(ranked) > 1 else None
        rows.append({
            "store": store,
            "item": item,
            "horizon_days": int(horizon),
            "models_evaluated": int(len(group)),
            "models_ranked": int(len(ranked)),
            "recommended_model": best["model"],
            "runner_up_model": runner_up["model"] if runner_up is not None else None,
            "mean_origin_WAPE (%)": float(best["mean_origin_WAPE (%)"]),
            "WAPE_std_across_origins (%)": float(best["WAPE_std_across_origins (%)"]),
            "runner_up_mean_origin_WAPE (%)": (
                float(runner_up["mean_origin_WAPE (%)"]) if runner_up is not None else float("nan")
            ),
            "WAPE_gap_vs_runner_up (pp)": (
                float(runner_up["mean_origin_WAPE (%)"] - best["mean_origin_WAPE (%)"])
                if runner_up is not None else float("nan")
            ),
            "pooled_WAPE (%)": float(best["WAPE (%)"]) if pd.notna(best["WAPE (%)"]) else float("nan"),
            "origins_evaluated": int(best["origins_evaluated"]),
            "evaluation_rows": int(best["evaluation_rows"]),
            "actual_units": float(best["actual_units"]),
            "selection_status": (
                "recommended_by_mean_origin_wape"
                if runner_up is not None else "only_one_model_with_defined_wape"
            ),
        })

    return pd.DataFrame(rows).sort_values(
        ["horizon_days", "store", "item"]
    ).reset_index(drop=True)


def rolling_origin_multi_horizon_backtest(
    data: pd.DataFrame,
    n_origins: int = 3,
    step_days: int = 15,
    max_train_rows: int = 200_000,
):
    """Evaluate recursive forecasts across multiple historical forecast origins.

    Each origin uses its own pre-origin training history and a 30-day holdout.
    Origins are spaced by step_days. Metrics pool forecasts across origins and
    report variation in origin-level WAPE for 7-, 15- and 30-day horizons.
    """
    if n_origins < 2:
        raise ValueError("n_origins must be at least 2 for rolling-origin evaluation.")
    if step_days < 1:
        raise ValueError("step_days must be at least 1.")
    if max_train_rows < 1:
        raise ValueError("max_train_rows must be at least 1.")

    missing = sorted(set(REQUIRED_COLUMNS) - set(data.columns))
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    if data.empty:
        raise ValueError("No sales rows are available for rolling-origin backtesting.")

    frame = data.loc[:, list(REQUIRED_COLUMNS)].copy()
    frame["date"] = pd.to_datetime(frame["date"], format="mixed", errors="coerce")
    frame["sales"] = pd.to_numeric(frame["sales"], errors="coerce")
    if frame[["date", "store", "item", "sales"]].isna().any().any():
        raise ValueError(
            "Rolling-origin backtesting requires valid dates, store/item identifiers "
            "and numeric sales. Clean invalid rows before evaluation."
        )
    if not np.isfinite(frame["sales"].to_numpy(dtype=float)).all():
        raise ValueError("Sales values must be finite numbers.")
    if frame["sales"].lt(0).any():
        raise ValueError("Sales values must be non-negative.")
    frame["date"] = frame["date"].dt.normalize()

    if frame.duplicated(["store", "item", "date"]).any():
        raise ValueError(
            "Rolling-origin backtesting requires one sales row per date, store and item. "
            "Aggregate duplicate daily records before evaluation."
        )

    frame = frame.sort_values(["store", "item", "date"]).reset_index(drop=True)
    unique_dates = pd.DatetimeIndex(sorted(frame["date"].drop_duplicates()))
    required_dates = 46 + (n_origins - 1) * step_days
    if len(unique_dates) < required_dates:
        raise ValueError(
            f"At least {required_dates} distinct daily dates are required for "
            f"{n_origins} origins spaced {step_days} days apart."
        )

    # Origins are ordered oldest to newest. Each holdout spans 30 consecutive days.
    end_indices = [
        len(unique_dates) - 1 - offset * step_days
        for offset in reversed(range(n_origins))
    ]
    origin_predictions = []
    origin_metrics = []
    origin_metadata = []

    for origin_number, end_index in enumerate(end_indices, start=1):
        origin_end = unique_dates[end_index]
        origin_start_index = end_index - 29
        if origin_start_index < 15:
            raise ValueError(
                "Insufficient pre-origin history. Each origin needs at least "
                "15 training days before its 30-day holdout."
            )
        origin_start = unique_dates[origin_start_index]
        origin_data = frame.loc[frame["date"].le(origin_end)].copy()

        metrics, predictions, metadata = recursive_multi_horizon_backtest(
            origin_data,
            max_train_rows=max_train_rows,
        )
        predictions["origin"] = origin_start
        predictions["origin_number"] = origin_number
        metrics["origin"] = origin_start
        metrics["origin_number"] = origin_number
        origin_predictions.append(predictions)
        origin_metrics.append(metrics)
        origin_metadata.append(metadata)

    all_predictions = pd.concat(origin_predictions, ignore_index=True)
    all_origin_metrics = pd.concat(origin_metrics, ignore_index=True)
    metric_rows = []

    for horizon in (7, 15, 30):
        horizon_predictions = all_predictions.loc[
            all_predictions["forecast_step"].le(horizon)
        ]
        for model_name, group in horizon_predictions.groupby("model"):
            errors = group["prediction"] - group["actual"]
            total_actual = float(group["actual"].sum())
            per_origin_wape = all_origin_metrics.loc[
                (all_origin_metrics["model"] == model_name)
                & (all_origin_metrics["horizon_days"] == horizon),
                "WAPE (%)",
            ]
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
                "mean_origin_WAPE (%)": float(per_origin_wape.mean()),
                "WAPE_std_across_origins (%)": float(per_origin_wape.std(ddof=0)),
                "origins_evaluated": int(per_origin_wape.count()),
            })

    metrics = pd.DataFrame(metric_rows).sort_values(
        ["horizon_days", "WAPE (%)"]
    ).reset_index(drop=True)
    metadata = {
        "origins_evaluated": int(len(origin_metadata)),
        "origin_spacing_days": int(step_days),
        "holdout_days_per_origin": 30,
        "first_origin_start": pd.Timestamp(origin_metadata[0]["holdout_start"]).date(),
        "last_origin_start": pd.Timestamp(origin_metadata[-1]["holdout_start"]).date(),
        "series_count": int(origin_metadata[-1]["series_count"]),
        "training_rows_used_per_origin": [
            int(item["training_rows_used"]) for item in origin_metadata
        ],
        "prediction_rows": int(len(all_predictions)),
        "evaluation_method": "rolling_origin_recursive_multi_step",
    }
    return metrics, all_predictions, metadata
