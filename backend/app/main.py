"""DemandIQ FastAPI application entry point."""
import logging
import os
from io import BytesIO

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from data_validation import validate_sales_data
from forecasting import forecast_future_demand

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
    horizon_days: int = 7,
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
