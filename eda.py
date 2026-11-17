"""Exploratory summaries and aggregations for validated DemandIQ sales data."""
import pandas as pd

REQUIRED_COLUMNS = ("date", "store", "item", "sales")


def _check_columns(data: pd.DataFrame) -> None:
    missing = sorted(set(REQUIRED_COLUMNS) - set(data.columns))
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))


def summarize_sales_data(data: pd.DataFrame) -> dict:
    """Return descriptive metrics for a validated sales dataframe."""
    _check_columns(data)
    if data.empty:
        return {"rows": 0, "date_start": None, "date_end": None, "days_covered": 0,
                "products": 0, "stores": 0, "total_units": 0.0, "avg_daily_units": 0.0,
                "median_daily_units": 0.0, "zero_sales_rows": 0}
    frame = data.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["sales"] = pd.to_numeric(frame["sales"], errors="coerce")
    frame = frame.dropna(subset=["date", "sales"])
    if frame.empty:
        return summarize_sales_data(pd.DataFrame(columns=REQUIRED_COLUMNS))
    daily = frame.groupby(frame["date"].dt.normalize())["sales"].sum()
    return {
        "rows": int(len(frame)), "date_start": frame["date"].min().date(),
        "date_end": frame["date"].max().date(),
        "days_covered": int(frame["date"].dt.normalize().nunique()),
        "products": int(frame["item"].nunique()), "stores": int(frame["store"].nunique()),
        "total_units": float(frame["sales"].sum()), "avg_daily_units": float(daily.mean()),
        "median_daily_units": float(daily.median()),
        "zero_sales_rows": int(frame["sales"].eq(0).sum()),
    }


def daily_sales(data: pd.DataFrame) -> pd.DataFrame:
    """Aggregate units sold by calendar date."""
    _check_columns(data)
    if data.empty:
        return pd.DataFrame(columns=["date", "sales"])
    frame = data.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["sales"] = pd.to_numeric(frame["sales"], errors="coerce")
    return (frame.dropna(subset=["date", "sales"]).groupby("date", as_index=False)["sales"]
            .sum().sort_values("date").reset_index(drop=True))


def top_products(data: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    """Return products ranked by total units sold."""
    _check_columns(data)
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if data.empty:
        return pd.DataFrame(columns=["item", "sales"])
    return data.groupby("item", as_index=False)["sales"].sum().nlargest(limit, "sales").reset_index(drop=True)


def store_sales(data: pd.DataFrame) -> pd.DataFrame:
    """Return stores ranked by total units sold."""
    _check_columns(data)
    if data.empty:
        return pd.DataFrame(columns=["store", "sales"])
    return data.groupby("store", as_index=False)["sales"].sum().sort_values(
        "sales", ascending=False
    ).reset_index(drop=True)


def weekday_sales(data: pd.DataFrame) -> pd.DataFrame:
    """Aggregate average sales by weekday in Monday-to-Sunday order."""
    _check_columns(data)
    columns = ["weekday", "sales"]
    if data.empty:
        return pd.DataFrame(columns=columns)
    frame = data.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["sales"] = pd.to_numeric(frame["sales"], errors="coerce")
    frame = frame.dropna(subset=["date", "sales"])
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    frame["weekday"] = pd.Categorical(frame["date"].dt.day_name(), categories=order, ordered=True)
    return (frame.groupby("weekday", observed=False, as_index=False)["sales"].mean()
            .sort_values("weekday").reset_index(drop=True))
