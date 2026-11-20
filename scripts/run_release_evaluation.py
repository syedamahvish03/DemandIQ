"""Reproducible Stage 6 evaluation for a real DemandIQ sales dataset.

Run from the repository root:
    python scripts/run_release_evaluation.py --input path/to/train.csv

The input CSV must contain date, store, item, sales and one daily row per
store-item-date. Results are written outside the source data by default.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from data_validation import validate_sales_data
from forecasting import (
    per_series_rolling_origin_metrics,
    recommend_per_series_models,
    recursive_multi_horizon_backtest,
    rolling_origin_multi_horizon_backtest,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run reproducible DemandIQ release evaluation.")
    parser.add_argument("--input", required=True, type=Path, help="Path to a real retail sales CSV.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/release_evaluation"),
        help="Directory for metrics and dataset profile (default: results/release_evaluation).",
    )
    parser.add_argument("--origins", type=int, default=3, help="Rolling forecast origins; minimum 2.")
    parser.add_argument("--step-days", type=int, default=15, help="Days between rolling origins.")
    parser.add_argument("--max-train-rows", type=int, default=200_000, help="Training-row cap per model fit.")
    return parser


def run_evaluation(input_path: Path, output_dir: Path, origins: int, step_days: int, max_train_rows: int) -> dict:
    if not input_path.is_file():
        raise FileNotFoundError(f"Input dataset was not found: {input_path}")
    if origins < 2 or step_days < 1 or max_train_rows < 1:
        raise ValueError("origins must be >= 2; step-days and max-train-rows must be positive.")

    raw = pd.read_csv(input_path)
    cleaned, quality = validate_sales_data(raw)
    if quality["errors"]:
        raise ValueError("Dataset validation failed: " + " ".join(quality["errors"]))
    if quality["duplicate_rows"]:
        raise ValueError(
            f"Dataset contains {quality['duplicate_rows']} duplicate daily store-item rows. "
            "Resolve or aggregate them using a documented business rule before evaluation."
        )

    cleaned["date"] = pd.to_datetime(cleaned["date"]).dt.normalize()
    series_counts = cleaned.groupby(["store", "item"], dropna=False).size()
    date_counts = cleaned.groupby(["store", "item"])["date"].nunique()
    if (series_counts != date_counts).any():
        raise ValueError("Each store-item series must have one record per observed date.")
    expected_days = pd.date_range(cleaned["date"].min(), cleaned["date"].max(), freq="D")
    irregular = []
    for (store, item), group in cleaned.groupby(["store", "item"], sort=False):
        observed = pd.DatetimeIndex(group["date"].drop_duplicates().sort_values())
        if not observed.equals(expected_days):
            irregular.append(f"{store}/{item}")
    if irregular:
        sample = ", ".join(irregular[:10])
        raise ValueError(
            "Every evaluated store-item series must have complete daily coverage "
            f"over the dataset date range. Irregular series include: {sample}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    multi_metrics, multi_predictions, multi_metadata = recursive_multi_horizon_backtest(
        cleaned, max_train_rows=max_train_rows
    )
    rolling_metrics, rolling_predictions, rolling_metadata = rolling_origin_multi_horizon_backtest(
        cleaned,
        n_origins=origins,
        step_days=step_days,
        max_train_rows=max_train_rows,
    )
    per_series = per_series_rolling_origin_metrics(rolling_predictions)
    recommendations = recommend_per_series_models(per_series)

    multi_metrics.to_csv(output_dir / "recursive_multi_horizon_metrics.csv", index=False)
    multi_predictions.to_csv(output_dir / "recursive_multi_horizon_predictions.csv", index=False)
    rolling_metrics.to_csv(output_dir / "rolling_origin_metrics.csv", index=False)
    per_series.to_csv(output_dir / "rolling_origin_per_series_metrics.csv", index=False)
    recommendations.to_csv(output_dir / "per_series_model_comparison.csv", index=False)

    profile = {
        "source_file_name": input_path.name,
        "rows_received": quality["rows_received"],
        "rows_valid": quality["rows_valid"],
        "rows_excluded": quality["rows_received"] - quality["rows_valid"],
        "date_start": cleaned["date"].min().date().isoformat(),
        "date_end": cleaned["date"].max().date().isoformat(),
        "distinct_dates": int(cleaned["date"].nunique()),
        "store_count": int(cleaned["store"].nunique()),
        "item_count": int(cleaned["item"].nunique()),
        "store_item_series": int(cleaned[["store", "item"]].drop_duplicates().shape[0]),
        "validation_report": quality,
        "recursive_multi_horizon_evaluation": multi_metadata,
        "rolling_origin_evaluation": rolling_metadata,
        "evaluation_caveats": [
            "Forecasts are recursive multi-step forecasts, not one-step predictions.",
            "Rolling-origin holdout windows may overlap when origins are spaced less than 30 days apart.",
            "Model rankings are evaluation guidance and do not automatically change the production model.",
            "The dataset does not supply on-hand inventory, supplier lead times, promotions or future events.",
            "No model accuracy or business-impact claim should be made beyond the exported measured metrics.",
        ],
    }
    (output_dir / "dataset_profile_and_methodology.json").write_text(
        json.dumps(profile, indent=2, default=str), encoding="utf-8"
    )
    return profile


def main() -> int:
    args = build_parser().parse_args()
    profile = run_evaluation(
        args.input, args.output_dir, args.origins, args.step_days, args.max_train_rows
    )
    print(json.dumps({
        "status": "success",
        "output_dir": str(args.output_dir.resolve()),
        "rows_valid": profile["rows_valid"],
        "store_item_series": profile["store_item_series"],
        "date_start": profile["date_start"],
        "date_end": profile["date_end"],
        "files_written": [
            "recursive_multi_horizon_metrics.csv",
            "recursive_multi_horizon_predictions.csv",
            "rolling_origin_metrics.csv",
            "rolling_origin_per_series_metrics.csv",
            "per_series_model_comparison.csv",
            "dataset_profile_and_methodology.json",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
