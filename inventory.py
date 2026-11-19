"""Inventory calculations using explicit store-provided stock and supplier inputs."""
import numpy as np
import pandas as pd

INVENTORY_COLUMNS = (
    "store", "item", "on_hand", "on_order", "backorders",
    "lead_time_days", "review_period_days",
)


def build_inventory_template(sales_data: pd.DataFrame) -> pd.DataFrame:
    """Create one blank stock-input row for each observed store-item pair."""
    missing = {"store", "item"} - set(sales_data.columns)
    if missing:
        raise ValueError("Sales data is missing columns: " + ", ".join(sorted(missing)))
    pairs = (
        sales_data[["store", "item"]]
        .drop_duplicates()
        .sort_values(["store", "item"])
        .reset_index(drop=True)
    )
    for column in INVENTORY_COLUMNS[2:]:
        pairs[column] = pd.Series([None] * len(pairs), dtype="object")
    return pairs.loc[:, list(INVENTORY_COLUMNS)]


def calculate_inventory_recommendations(
    sales_data: pd.DataFrame,
    inventory_data: pd.DataFrame,
    lookback_days: int = 28,
    service_level_z: float = 1.65,
    demand_forecast: pd.DataFrame | None = None,
):
    """Calculate reorder points and order quantities for complete stock-input rows.

    Historical demand statistics are calculated from the latest lookback window.
    When a future forecast is supplied, forecast totals determine lead-time demand
    and the lead-time-plus-review target. Historical variability still determines
    safety stock. Stock values are never inferred.
    """
    sales_required = {"date", "store", "item", "sales"}
    missing_sales = sales_required - set(sales_data.columns)
    if missing_sales:
        raise ValueError("Sales data is missing columns: " + ", ".join(sorted(missing_sales)))
    missing_inventory = set(INVENTORY_COLUMNS) - set(inventory_data.columns)
    if missing_inventory:
        raise ValueError(
            "Inventory data is missing columns: " + ", ".join(sorted(missing_inventory))
        )
    if lookback_days < 1:
        raise ValueError("lookback_days must be at least 1")
    if not np.isfinite(service_level_z) or service_level_z < 0:
        raise ValueError("service_level_z must be a finite, non-negative number")

    stock = inventory_data.loc[:, list(INVENTORY_COLUMNS)].copy()
    if stock.duplicated(["store", "item"]).any():
        raise ValueError("Inventory input must contain only one row per store-item pair.")

    numeric_columns = list(INVENTORY_COLUMNS[2:])
    for column in numeric_columns:
        stock[column] = pd.to_numeric(stock[column], errors="coerce")

    required_values = numeric_columns
    complete_mask = stock[required_values].notna().all(axis=1)
    complete = stock.loc[complete_mask].copy()
    excluded_rows = int((~complete_mask).sum())
    if complete.empty:
        return pd.DataFrame(), {"excluded_input_rows": excluded_rows, "lookback_days": lookback_days}

    nonnegative_columns = ["on_hand", "on_order", "backorders", "lead_time_days", "review_period_days"]
    if not np.isfinite(complete[numeric_columns].to_numpy(dtype=float)).all():
        raise ValueError("Complete inventory inputs must contain finite numbers.")
    if (complete[nonnegative_columns] < 0).any().any():
        raise ValueError("Stock, order, backorder and time inputs cannot be negative.")
    day_columns = ["lead_time_days", "review_period_days"]
    if (complete[day_columns] % 1 != 0).any().any():
        raise ValueError("lead_time_days and review_period_days must be whole numbers of days.")
    if (complete["lead_time_days"] <= 0).any():
        raise ValueError("lead_time_days must be greater than zero.")
    if (complete["review_period_days"] <= 0).any():
        raise ValueError("review_period_days must be greater than zero.")

    sales = sales_data.loc[:, ["date", "store", "item", "sales"]].copy()
    sales["date"] = pd.to_datetime(sales["date"], errors="coerce")
    sales["sales"] = pd.to_numeric(sales["sales"], errors="coerce")
    sales = sales.dropna(subset=["date", "store", "item", "sales"])
    if sales.empty:
        raise ValueError("No valid sales observations are available.")
    end_date = sales["date"].max().normalize()
    start_date = end_date - pd.Timedelta(days=lookback_days - 1)
    recent = sales.loc[sales["date"].between(start_date, end_date)]
    demand = (
        recent.groupby(["store", "item"])["sales"]
        .agg(avg_daily_demand="mean", daily_demand_std="std", demand_records="count")
        .reset_index()
    )
    demand["daily_demand_std"] = demand["daily_demand_std"].fillna(0.0)

    result = complete.merge(demand, on=["store", "item"], how="left")
    result = result.dropna(subset=["avg_daily_demand"]).copy()
    if result.empty:
        return pd.DataFrame(), {
            "excluded_input_rows": excluded_rows + len(complete),
            "lookback_days": lookback_days,
        }

    result["safety_stock"] = (
        service_level_z
        * result["daily_demand_std"]
        * np.sqrt(result["lead_time_days"])
    )

    if demand_forecast is not None:
        forecast_required = {"date", "store", "item", "forecast_sales"}
        missing_forecast = forecast_required - set(demand_forecast.columns)
        if missing_forecast:
            raise ValueError(
                "Demand forecast is missing columns: "
                + ", ".join(sorted(missing_forecast))
            )
        forecast = demand_forecast.loc[:, list(forecast_required)].copy()
        forecast["date"] = pd.to_datetime(forecast["date"], errors="coerce").dt.normalize()
        forecast["forecast_sales"] = pd.to_numeric(
            forecast["forecast_sales"], errors="coerce"
        )
        if forecast[["date", "store", "item", "forecast_sales"]].isna().any().any():
            raise ValueError("Demand forecast contains invalid dates, identifiers or values.")
        if not np.isfinite(forecast["forecast_sales"].to_numpy(dtype=float)).all():
            raise ValueError("Forecast demand must contain finite numeric values.")
        if (forecast["forecast_sales"] < 0).any():
            raise ValueError("Forecast demand cannot be negative.")
        if forecast.duplicated(["store", "item", "date"]).any():
            raise ValueError("Demand forecast must contain one row per date and store-item pair.")

        forecast = forecast.sort_values(["store", "item", "date"])
        for key, group in forecast.groupby(["store", "item"], sort=False):
            if group["date"].diff().dropna().ne(pd.Timedelta(days=1)).any():
                raise ValueError(
                    f"Forecast dates must be consecutive daily observations for "
                    f"store {key[0]}, item {key[1]}."
                )
        forecast_groups = {
            key: group["forecast_sales"].to_numpy(dtype=float)
            for key, group in forecast.groupby(["store", "item"], sort=False)
        }
        lead_demands = []
        protection_demands = []
        for row in result.itertuples(index=False):
            key = (row.store, row.item)
            if key not in forecast_groups:
                raise ValueError(
                    f"No future demand forecast is available for store {row.store}, item {row.item}."
                )
            values = forecast_groups[key]
            lead_days = int(row.lead_time_days)
            protection_days = lead_days + int(row.review_period_days)
            if len(values) < protection_days:
                raise ValueError(
                    f"Forecast horizon is too short for store {row.store}, item {row.item}. "
                    f"At least {protection_days} forecast days are required."
                )
            lead_demands.append(float(values[:lead_days].sum()))
            protection_demands.append(float(values[:protection_days].sum()))

        result["forecast_lead_demand"] = lead_demands
        result["forecast_protection_demand"] = protection_demands
        result["demand_basis"] = "future_forecast"
        result["reorder_point"] = (
            result["forecast_lead_demand"] + result["safety_stock"]
        )
        result["target_stock"] = (
            result["forecast_protection_demand"] + result["safety_stock"]
        )
    else:
        result["demand_basis"] = "historical_average"
        result["reorder_point"] = (
            result["avg_daily_demand"] * result["lead_time_days"]
            + result["safety_stock"]
        )
        result["target_stock"] = (
            result["avg_daily_demand"]
            * (result["lead_time_days"] + result["review_period_days"])
            + result["safety_stock"]
        )

    result["inventory_position"] = (
        result["on_hand"] + result["on_order"] - result["backorders"]
    )
    result["recommended_order_qty"] = (
        result["target_stock"] - result["inventory_position"]
    ).clip(lower=0).apply(np.ceil).astype(int)
    result["reorder_required"] = result["inventory_position"] <= result["reorder_point"]

    result = result.sort_values(
        ["recommended_order_qty", "avg_daily_demand"],
        ascending=[False, False],
    ).reset_index(drop=True)
    metadata = {
        "excluded_input_rows": excluded_rows,
        "lookback_days": lookback_days,
        "demand_window_start": start_date.date(),
        "demand_window_end": end_date.date(),
        "complete_recommendations": int(len(result)),
        "demand_basis": "future_forecast" if demand_forecast is not None else "historical_average",
    }
    return result, metadata


def build_illustrative_inventory_inputs(
    sales_data: pd.DataFrame,
    stock_cover_days: int = 7,
    lead_time_days: int = 7,
    review_period_days: int = 7,
) -> pd.DataFrame:
    """Build explicitly illustrative stock inputs from recent sales, never real stock data.

    On-hand stock is assumed to equal recent average daily sales multiplied by
    the selected stock-cover days. Incoming orders and backorders are assumed
    to be zero. Lead time and review period are scenario assumptions.
    """
    if min(stock_cover_days, lead_time_days, review_period_days) < 1:
        raise ValueError("Illustrative scenario settings must be at least 1 day.")
    required = {"date", "store", "item", "sales"}
    missing = required - set(sales_data.columns)
    if missing:
        raise ValueError("Sales data is missing columns: " + ", ".join(sorted(missing)))

    sales = sales_data.loc[:, ["date", "store", "item", "sales"]].copy()
    sales["date"] = pd.to_datetime(sales["date"], errors="coerce")
    sales["sales"] = pd.to_numeric(sales["sales"], errors="coerce")
    sales = sales.dropna(subset=["date", "store", "item", "sales"])
    if sales.empty:
        raise ValueError("No valid sales observations are available.")

    end_date = sales["date"].max().normalize()
    start_date = end_date - pd.Timedelta(days=27)
    recent = sales.loc[sales["date"].between(start_date, end_date)]
    averages = (
        recent.groupby(["store", "item"])["sales"]
        .mean()
        .rename("avg_daily_demand")
        .reset_index()
    )
    averages["on_hand"] = np.ceil(averages["avg_daily_demand"] * stock_cover_days)
    averages["on_order"] = 0
    averages["backorders"] = 0
    averages["lead_time_days"] = lead_time_days
    averages["review_period_days"] = review_period_days
    return averages.loc[:, list(INVENTORY_COLUMNS)]
