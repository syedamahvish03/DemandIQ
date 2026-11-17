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
    for (store, item), history in histories.items():
        values = history["sales"]
        next_date = history["last_date"] + pd.Timedelta(days=1)
        for step in range(horizon_days):
            current_date = next_date + pd.Timedelta(days=step)
            feature_row = pd.DataFrame([{
                "lag_1": values[-1],
                "lag_7": values[-7],
                "lag_14": values[-14],
                "rolling_mean_7": float(np.mean(values[-7:])),
                "rolling_mean_14": float(np.mean(values[-14:])),
                "day_of_week": current_date.day_of_week,
                "month": current_date.month,
                "day_of_month": current_date.day,
                "year": current_date.year,
            }])
            prediction = max(0.0, float(model.predict(feature_row[feature_columns])[0]))
            forecast_rows.append({
                "date": current_date,
                "store": store,
                "item": item,
                "forecast_sales": prediction,
                "forecast_step": step + 1,
            })
            values.append(prediction)

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
