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
    frame["day_of_week"] = frame["date"].dt.dayofweek
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
