from pathlib import Path

import pandas as pd

from data_loader import load_sales_csv


def test_load_sales_csv_reads_and_validates_file(tmp_path: Path):
    path = tmp_path / "sales.csv"
    pd.DataFrame({
        "date": ["2025-01-01", "2025-01-02"],
        "store": [1, 1],
        "item": [101, 102],
        "sales": [10, 12],
    }).to_csv(path, index=False)

    cleaned, report = load_sales_csv(path)

    assert report["errors"] == []
    assert report["rows_received"] == 2
    assert report["rows_valid"] == 2
    assert cleaned["sales"].tolist() == [10.0, 12.0]


def test_load_sales_csv_reports_missing_columns(tmp_path: Path):
    path = tmp_path / "bad.csv"
    pd.DataFrame({"date": ["2025-01-01"], "sales": [10]}).to_csv(path, index=False)

    cleaned, report = load_sales_csv(path)

    assert cleaned.empty
    assert any("Missing required columns" in error for error in report["errors"])
