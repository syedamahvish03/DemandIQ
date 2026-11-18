# DemandIQ Backend

The backend is being introduced incrementally with FastAPI. This first milestone
adds the API application, configurable development CORS, and a health endpoint.
It does not yet connect authentication, Supabase, or customer data.

## Requirements

- Python 3.10 or newer
- The repository's existing Python virtual environment is recommended

## Install

Run these commands from the repository root:

```powershell
python -m pip install -r backend/requirements.txt
```

## Run the API

Run from the repository root:

```powershell
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Endpoints:

- `http://127.0.0.1:8000/` — API information
- `http://127.0.0.1:8000/api/v1/health` — health check
- `http://127.0.0.1:8000/docs` — interactive API documentation

## Run backend tests

From the repository root:

```powershell
python -m pytest backend/tests -q
```

## CORS configuration

The development frontend origins are allowed by default:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

Set `DEMANDIQ_CORS_ORIGINS` to a comma-separated list of exact origins when
the frontend runs at a different address. Do not use a wildcard in production.

## Current boundary

The health endpoint confirms that the frontend can reach the API. It does not
mean database, Supabase authentication, tenant isolation, or forecasting routes
are connected yet. Those will be added in reviewed, independently tested steps.
