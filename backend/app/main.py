"""DemandIQ FastAPI application entry point."""
import logging
import os
from io import BytesIO

from fastapi.responses import Response

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from data_validation import validate_sales_data
from forecasting import forecast_future_demand
from inventory import INVENTORY_COLUMNS, build_inventory_template, calculate_inventory_recommendations

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_HORIZONS = (7, 15, 30)


def get_allowed_origins() -> list[str]:
    """Read explicitly allowed browser origins from the environment."""
    configured = os.getenv("DEMANDIQ_CORS_ORIGINS")
    if not configured:
        return list(DEFAULT_ALLOWED_ORIGINS)
    origins = [origin.strip().rstrip("/") for origin in configured.split(",")]
    return [origin for origin in origins if origin]


app = FastAPI(
    title="DemandIQ API",
    description="Backend API for the DemandIQ retail intelligence platform.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Accept", "Content-Type"],
)


@app.get("/", tags=["System"])
def read_root() -> dict[str, str]:
    """Return basic API information."""
    return {"service": "DemandIQ API", "status": "ok", "docs": "/docs"}


@app.get("/api/v1/health", tags=["System"])
def health_check() -> dict[str, str]:
    """Provide a lightweight endpoint for frontend/API connectivity checks."""
    return {"service": "DemandIQ API", "status": "ok", "version": app.version}


@app.post("/api/v1/forecasts", tags=["Forecasting"])
async def create_forecast(
    file: UploadFile = File(..., description="Historical sales CSV file"),
    horizon_days: int = Form(7),
) -> dict:
    """Validate uploaded sales history and generate a future demand forecast."""
    if horizon_days not in ALLOWED_HORIZONS:
        raise HTTPException(
            status_code=422,
            detail="horizon_days must be one of 7, 15 or 30.",
        )

    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Please upload a CSV file.")

    raw_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="The uploaded CSV file is empty.")
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="The CSV file exceeds the 10 MB upload limit.",
        )

    try:
        uploaded_data = pd.read_csv(BytesIO(raw_bytes))
    except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError):
        raise HTTPException(
            status_code=400,
            detail="The file could not be read as a valid CSV. Check its encoding and formatting.",
        ) from None

    cleaned_data, quality_report = validate_sales_data(uploaded_data)
    if quality_report["errors"]:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "The sales file did not pass data validation.",
                "quality_report": quality_report,
            },
        )

    try:
        forecast, metadata = forecast_future_demand(
            cleaned_data,
            horizon_days=horizon_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception:
        logger.exception("Unexpected error while generating a demand forecast.")
        raise HTTPException(
            status_code=500,
            detail="The forecast could not be generated due to an internal processing error.",
        ) from None

    forecast_records = forecast.copy()
    forecast_records["date"] = pd.to_datetime(
        forecast_records["date"]
    ).dt.strftime("%Y-%m-%d")

    return {
        "status": "success",
        "model": "random_forest",
        "metadata": {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in metadata.items()
        },
        "quality_report": quality_report,
        "forecast": forecast_records.to_dict(orient="records"),
    }


def _read_csv_upload(raw_bytes: bytes, label: str) -> pd.DataFrame:
    """Parse a bounded CSV upload and return a clear client-facing error."""
    if not raw_bytes:
        raise HTTPException(status_code=400, detail=f"The {label} CSV file is empty.")
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"The {label} CSV exceeds the 10 MB upload limit.")
    try:
        frame = pd.read_csv(BytesIO(raw_bytes))
    except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError):
        raise HTTPException(
            status_code=400,
            detail=f"The {label} file could not be read as a valid CSV. Check its encoding and formatting.",
        ) from None
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    return frame


@app.post("/api/v1/inventory/template", tags=["Inventory"])
async def create_inventory_template(
    sales_file: UploadFile = File(..., description="Validated historical sales CSV"),
) -> Response:
    """Create a blank stock-input template for the store-item pairs in sales history."""
    if not (sales_file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Please upload a sales CSV file.")
    sales_raw = await sales_file.read(MAX_UPLOAD_BYTES + 1)
    sales_frame = _read_csv_upload(sales_raw, "sales")
    cleaned_sales, quality_report = validate_sales_data(sales_frame)
    if quality_report["errors"]:
        raise HTTPException(
            status_code=422,
            detail={"message": "The sales file did not pass data validation.", "quality_report": quality_report},
        )
    template = build_inventory_template(cleaned_sales)
    csv_content = template.to_csv(index=False)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="demandiq_inventory_template.csv"'},
    )


@app.post("/api/v1/inventory/recommendations", tags=["Inventory"])
async def create_inventory_recommendations(
    sales_file: UploadFile = File(..., description="Historical daily sales CSV"),
    inventory_file: UploadFile = File(..., description="Completed inventory-input CSV"),
    lookback_days: int = Form(28),
    service_level_z: float = Form(1.65),
    forecast_horizon_days: int | None = Form(None),
) -> dict:
    """Generate inventory guidance; forecast mode is opt-in for API compatibility."""
    if forecast_horizon_days is not None and forecast_horizon_days not in ALLOWED_HORIZONS:
        raise HTTPException(
            status_code=422,
            detail="forecast_horizon_days must be one of 7, 15 or 30.",
        )

    for upload, label in ((sales_file, "sales"), (inventory_file, "inventory")):
        if not (upload.filename or "").lower().endswith(".csv"):
            raise HTTPException(status_code=415, detail=f"Please upload a {label} CSV file.")

    sales_raw = await sales_file.read(MAX_UPLOAD_BYTES + 1)
    inventory_raw = await inventory_file.read(MAX_UPLOAD_BYTES + 1)
    sales_frame = _read_csv_upload(sales_raw, "sales")
    inventory_frame = _read_csv_upload(inventory_raw, "inventory")

    cleaned_sales, quality_report = validate_sales_data(sales_frame)
    if quality_report["errors"]:
        raise HTTPException(
            status_code=422,
            detail={"message": "The sales file did not pass data validation.", "quality_report": quality_report},
        )

    missing_inventory_columns = sorted(set(INVENTORY_COLUMNS) - set(inventory_frame.columns))
    if missing_inventory_columns:
        raise HTTPException(
            status_code=422,
            detail="Inventory CSV is missing required columns: " + ", ".join(missing_inventory_columns),
        )

    try:
        forecast_metadata = None
        demand_forecast = None
        if forecast_horizon_days is not None:
            demand_forecast, forecast_metadata = forecast_future_demand(
                cleaned_sales,
                horizon_days=forecast_horizon_days,
            )
        recommendations, metadata = calculate_inventory_recommendations(
            cleaned_sales,
            inventory_frame.loc[:, list(INVENTORY_COLUMNS)],
            lookback_days=lookback_days,
            service_level_z=service_level_z,
            demand_forecast=demand_forecast,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception:
        logger.exception("Unexpected error while generating forecast-driven inventory recommendations.")
        raise HTTPException(
            status_code=500,
            detail="Inventory recommendations could not be generated due to an internal processing error.",
        ) from None

    metadata = {
        key: value.isoformat() if hasattr(value, "isoformat") else value
        for key, value in metadata.items()
    }
    records = recommendations.astype(object).where(pd.notna(recommendations), None).to_dict(orient="records")
    response_metadata = dict(metadata)
    if forecast_metadata is not None:
        response_metadata.update({
            "forecast_horizon_days": forecast_metadata["horizon_days"],
            "forecast_rows": forecast_metadata["forecast_rows"],
            "forecast_start": forecast_metadata["forecast_start"].isoformat(),
            "forecast_end": forecast_metadata["forecast_end"].isoformat(),
        })

    return {
        "status": "success",
        "demand_basis": metadata["demand_basis"],
        "metadata": response_metadata,
        "sales_quality_report": quality_report,
        "recommendations": records,
    }
