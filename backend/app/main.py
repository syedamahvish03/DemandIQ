"""DemandIQ FastAPI application entry point.

This first backend milestone provides a small, testable API foundation.
Business endpoints will be added only after their data contracts are defined.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


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
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Accept", "Content-Type"],
)


@app.get("/", tags=["System"])
def read_root() -> dict[str, str]:
    """Return basic API information."""
    return {
        "service": "DemandIQ API",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/api/v1/health", tags=["System"])
def health_check() -> dict[str, str]:
    """Provide a lightweight endpoint for frontend/API connectivity checks."""
    return {
        "service": "DemandIQ API",
        "status": "ok",
        "version": app.version,
    }
