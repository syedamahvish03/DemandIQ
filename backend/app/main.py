"""DemandIQ FastAPI application entry point."""
import logging
import os
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

# Load backend-local settings for development; hosted environments use platform env vars.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
from io import BytesIO

from fastapi.responses import Response

import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import httpx
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from data_validation import validate_sales_data
from forecasting import forecast_future_demand
from inventory import INVENTORY_COLUMNS, build_inventory_template, calculate_inventory_recommendations

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
# Includes both maximum-size inventory CSVs plus multipart/form overhead.
MAX_REQUEST_BODY_BYTES = 21 * 1024 * 1024
ALLOWED_HORIZONS = (7, 15, 30)


RATE_LIMITED_PATHS = {
    "/api/v1/forecasts",
    "/api/v1/sales/validate",
    "/api/v1/inventory/template",
    "/api/v1/inventory/recommendations",
}
_rate_limit_lock = threading.Lock()
_rate_limit_buckets: dict[str, tuple[float, int]] = {}


def _rate_limit_settings() -> tuple[int, int]:
    """Return safe per-process request and time-window limits."""
    try:
        limit = int(os.getenv("DEMANDIQ_API_RATE_LIMIT_REQUESTS", "120"))
        window = int(os.getenv("DEMANDIQ_API_RATE_LIMIT_WINDOW_SECONDS", "60"))
    except ValueError:
        return 120, 60
    if limit < 1 or window < 1:
        return 120, 60
    return limit, window



def get_allowed_origins() -> list[str]:
    """Read explicitly allowed browser origins from the environment."""
    configured = os.getenv("DEMANDIQ_CORS_ORIGINS")
    if not configured:
        return list(DEFAULT_ALLOWED_ORIGINS)
    origins = [origin.strip().rstrip("/") for origin in configured.split(",")]
    return [origin for origin in origins if origin]


security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Validate a Supabase access token against the Supabase Auth user endpoint."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Authentication is required to use this processing endpoint.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    if not supabase_url or not publishable_key:
        logger.error("Supabase API authentication is not configured.")
        raise HTTPException(
            status_code=503,
            detail="Authentication service is not configured.",
        )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{supabase_url}/auth/v1/user",
                headers={
                    "apikey": publishable_key,
                    "Authorization": f"Bearer {credentials.credentials}",
                },
            )
    except httpx.RequestError:
        logger.warning("Unable to reach Supabase Auth to validate an API access token.")
        raise HTTPException(
            status_code=503,
            detail="Authentication service is temporarily unavailable.",
        ) from None

    if response.status_code in (400, 401, 403):
        raise HTTPException(
            status_code=401,
            detail="The authentication token is invalid or has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if response.status_code != 200:
        logger.warning("Supabase Auth returned HTTP %s during token validation.", response.status_code)
        raise HTTPException(
            status_code=503,
            detail="Authentication service is temporarily unavailable.",
        )

    try:
        user = response.json()
    except ValueError:
        user = None
    if not isinstance(user, dict) or not user.get("id"):
        raise HTTPException(
            status_code=401,
            detail="The authentication service returned an invalid user.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"id": str(user["id"])}


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
    allow_headers=["Accept", "Content-Type", "Authorization"],
)


@app.middleware("http")
async def limit_processing_requests(request: Request, call_next):
    """Apply a conservative per-client abuse limit to CPU/memory-heavy upload APIs.

    This in-process guard is defense in depth. Production deployments must also
    enforce distributed limits and body/time limits at the hosting edge.
    """
    if request.method == "POST" and request.url.path in RATE_LIMITED_PATHS:
        client_host = request.client.host if request.client else "unknown"
        now = time.monotonic()
        limit, window = _rate_limit_settings()
        with _rate_limit_lock:
            bucket = _rate_limit_buckets.get(client_host)
            if bucket is None and len(_rate_limit_buckets) >= 5000:
                # Remove only expired clients; never clear active limits to make room.
                expired_clients = [
                    host
                    for host, (started_at, _) in _rate_limit_buckets.items()
                    if now - started_at >= window
                ]
                for host in expired_clients:
                    del _rate_limit_buckets[host]
                if len(_rate_limit_buckets) >= 5000:
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Processing capacity is temporarily limited. Please retry shortly."},
                        headers={"Retry-After": str(window)},
                    )

            started_at, count = bucket if bucket is not None else (now, 0)
            if now - started_at >= window:
                started_at, count = now, 0
            if count >= limit:
                retry_after = max(1, int(window - (now - started_at)))
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many processing requests. Please wait before trying again."},
                    headers={"Retry-After": str(retry_after)},
                )
            _rate_limit_buckets[client_host] = (started_at, count + 1)

        # Bound the complete multipart request, not only each individual CSV.
        # The 21 MiB cap leaves 1 MiB for multipart boundaries and form fields
        # while allowing two CSV files at the existing 10 MiB per-file limit.
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                declared_length = int(content_length)
            except ValueError:
                declared_length = None
            if declared_length is not None and declared_length > MAX_REQUEST_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "The total upload request exceeds the 21 MB request limit."},
                )

        received_body = bytearray()
        async for chunk in request.stream():
            received_body.extend(chunk)
            if len(received_body) > MAX_REQUEST_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "The total upload request exceeds the 21 MB request limit."},
                )
        # Cache the bounded body so Starlette's downstream request stream
        # and FastAPI's multipart parser can read it without consuming the
        # original ASGI receive channel twice.
        request._body = bytes(received_body)

    return await call_next(request)



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
    _current_user: dict = Depends(get_current_user),
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


@app.post("/api/v1/sales/validate", tags=["Sales"])
async def validate_sales_upload(
    file: UploadFile = File(..., description="Historical sales CSV file to preview before import"),
    include_records: bool = False,
    _current_user: dict = Depends(get_current_user),
) -> dict:
    """Validate a sales CSV and return a safe preview without persisting uploaded data."""
    if not (file.filename or "").strip().lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Please upload a CSV file.")

    raw_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    sales_frame = _read_csv_upload(raw_bytes, "sales")
    cleaned_sales, quality_report = validate_sales_data(sales_frame)

    preview = cleaned_sales.head(20).copy()
    if not preview.empty:
        preview["date"] = pd.to_datetime(preview["date"]).dt.strftime("%Y-%m-%d")
    preview_records = preview.to_dict(orient="records")

    blocking_issues = list(quality_report["errors"])
    if quality_report["duplicate_rows"]:
        blocking_issues.append(
            "Duplicate store-item calendar dates must be resolved before importing this file."
        )

    response = {
        "status": "success",
        "can_import": not blocking_issues and quality_report["rows_valid"] > 0,
        "preview_limit": 20,
        "preview_rows": preview_records,
        "quality_report": quality_report,
        "blocking_issues": blocking_issues,
        "excluded_rows": quality_report["rows_received"] - quality_report["rows_valid"],
    }
    if include_records and response["can_import"]:
        all_records = cleaned_sales.copy()
        all_records["date"] = pd.to_datetime(all_records["date"]).dt.strftime("%Y-%m-%d")
        response["validated_rows"] = all_records.to_dict(orient="records")
    return response


@app.post("/api/v1/inventory/template", tags=["Inventory"])
async def create_inventory_template(
    sales_file: UploadFile = File(..., description="Validated historical sales CSV"),
    _current_user: dict = Depends(get_current_user),
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
    _current_user: dict = Depends(get_current_user),
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
        inventory_inputs = inventory_frame.loc[:, list(INVENTORY_COLUMNS)].copy()
        excluded_forecast_rows = 0
        if forecast_horizon_days is not None:
            demand_forecast, forecast_metadata = forecast_future_demand(
                cleaned_sales,
                horizon_days=forecast_horizon_days,
            )
            forecast_pairs = pd.MultiIndex.from_frame(
                demand_forecast[["store", "item"]].drop_duplicates()
            )
            numeric_inventory = inventory_inputs.loc[:, list(INVENTORY_COLUMNS[2:])].apply(
                pd.to_numeric, errors="coerce"
            )
            complete_stock_mask = numeric_inventory.notna().all(axis=1)
            inventory_pairs = pd.MultiIndex.from_frame(
                inventory_inputs[["store", "item"]]
            )
            has_forecast_mask = inventory_pairs.isin(forecast_pairs)
            excluded_forecast_mask = complete_stock_mask & ~has_forecast_mask
            excluded_forecast_rows = int(excluded_forecast_mask.sum())
            inventory_inputs = inventory_inputs.loc[~excluded_forecast_mask].copy()

        recommendations, metadata = calculate_inventory_recommendations(
            cleaned_sales,
            inventory_inputs,
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
        response_metadata["excluded_forecast_rows"] = excluded_forecast_rows
        response_metadata.update({
            "forecast_horizon_days": forecast_metadata["horizon_days"],
            "forecast_rows": forecast_metadata["forecast_rows"],
            "forecast_start": forecast_metadata["forecast_start"].isoformat(),
            "forecast_end": forecast_metadata["forecast_end"].isoformat(),
            "forecast_total_series_count": forecast_metadata["total_series_count"],
            "forecast_excluded_series_count": forecast_metadata["excluded_series_count"],
            "forecast_excluded_series": forecast_metadata["excluded_series"],
        })

    return {
        "status": "success",
        "demand_basis": metadata["demand_basis"],
        "metadata": response_metadata,
        "sales_quality_report": quality_report,
        "recommendations": records,
    }
