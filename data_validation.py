"""Reusable validation and cleaning for DemandIQ retail sales CSV files."""
import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ("date", "store", "item", "sales")


def validate_sales_data(data: pd.DataFrame):
    """Return (clean_dataframe, report) without silently discarding duplicate records."""
    report = {
        "rows_received": int(len(data)),
        "rows_valid": 0,
        "invalid_dates": 0,
        "invalid_sales": 0,
        "negative_sales": 0,
        "missing_identifiers": 0,
        "duplicate_rows": 0,
        "errors": [],
        "warnings": [],
    }

    # Normalize header names so harmless capitalization and spaces do not break uploads.
    df = data.copy()
    df.columns = [str(column).strip().lower() for column in df.columns]
    missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        report["errors"].append("Missing required columns: " + ", ".join(missing))
        return pd.DataFrame(columns=REQUIRED_COLUMNS), report
    if df.empty:
        report["errors"].append("The uploaded CSV contains no data rows.")
        return pd.DataFrame(columns=REQUIRED_COLUMNS), report

    df = df.loc[:, list(REQUIRED_COLUMNS)].copy()
    # Normalize textual identifiers and treat empty/whitespace-only values as missing.
    for column in ("store", "item"):
        df[column] = df[column].map(
            lambda value: value.strip() if isinstance(value, str) else value
        )

    parsed_dates = pd.to_datetime(df["date"], errors="coerce")
    numeric_sales = pd.to_numeric(df["sales"], errors="coerce")
    invalid_dates = parsed_dates.isna()
    finite_sales = pd.Series(
        np.isfinite(numeric_sales.fillna(0).to_numpy(dtype=float)),
        index=numeric_sales.index,
    )
    invalid_sales = numeric_sales.isna() | ~finite_sales
    negative_sales = numeric_sales.lt(0).fillna(False) & finite_sales
    blank_identifiers = df[["store", "item"]].apply(
        lambda column: column.map(
            lambda value: isinstance(value, str) and not value.strip()
        )
    )
    missing_identifiers = (
        df["store"].isna() | df["item"].isna() | blank_identifiers.any(axis=1)
    )

    report["invalid_dates"] = int(invalid_dates.sum())
    report["invalid_sales"] = int(invalid_sales.sum())
    report["negative_sales"] = int(negative_sales.sum())
    report["missing_identifiers"] = int(missing_identifiers.sum())
    daily_keys = pd.DataFrame({
        "date": parsed_dates.dt.normalize(),
        "store": df["store"],
        "item": df["item"],
    })
    report["duplicate_rows"] = int(
        daily_keys.duplicated(subset=["date", "store", "item"]).sum()
    )

    valid_mask = ~(invalid_dates | invalid_sales | negative_sales | missing_identifiers)
    cleaned = df.loc[valid_mask].copy()
    cleaned["date"] = parsed_dates.loc[valid_mask]
    cleaned["sales"] = numeric_sales.loc[valid_mask].astype(float)
    report["rows_valid"] = int(len(cleaned))

    if report["invalid_dates"]:
        report["warnings"].append(f"{report['invalid_dates']} row(s) have invalid or missing dates and were excluded.")
    if report["invalid_sales"]:
        report["warnings"].append(f"{report['invalid_sales']} row(s) have missing, non-numeric or non-finite sales and were excluded.")
    if report["negative_sales"]:
        report["warnings"].append(f"{report['negative_sales']} row(s) have negative sales and were excluded.")
    if report["missing_identifiers"]:
        report["warnings"].append(f"{report['missing_identifiers']} row(s) have a missing store or item identifier and were excluded.")
    if report["duplicate_rows"]:
        report["warnings"].append(
            f"{report['duplicate_rows']} duplicate daily store-item date record(s) detected. They are retained for review; forecasting requires one row per store-item per calendar day."
        )
    if cleaned.empty:
        report["errors"].append("No usable rows remain after validation.")

    return cleaned.reset_index(drop=True), report
