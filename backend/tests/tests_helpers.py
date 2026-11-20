"""Small local fixture helper for API boundary tests."""
import pandas as pd


def make_sales_csv_for_hardening(days: int = 35) -> bytes:
    dates = pd.date_range("2025-01-01", periods=days, freq="D")
    frame = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "store": ["STORE_A"] * days,
        "item": ["SKU_100"] * days,
        "sales": [10 + (index % 4) for index in range(days)],
    })
    return frame.to_csv(index=False).encode("utf-8")
