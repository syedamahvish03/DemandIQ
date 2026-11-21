# DemandIQ FastAPI Backend

The FastAPI service exposes the existing Python sales validation, demand forecasting and inventory calculation modules to the React application. It is stateless: uploaded CSVs are processed for each request and are not written to Supabase by the API.

## Requirements and startup

Run from the repository root using the project's Python virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: `http://127.0.0.1:8000/api/v1/health`. Interactive API docs: `http://127.0.0.1:8000/docs`.

## Endpoints

| Method and path | Purpose |
|---|---|
| `GET /` | Basic service information |
| `GET /api/v1/health` | Lightweight API health check |
| `POST /api/v1/sales/validate` | Validate a sales CSV and return quality report and preview; `include_records=true` returns cleaned rows for the authenticated frontend import workflow |
| `POST /api/v1/forecasts` | Generate a 7-, 15- or 30-day Random Forest forecast |
| `POST /api/v1/inventory/template` | Return a blank stock-input CSV for store-item pairs |
| `POST /api/v1/inventory/recommendations` | Calculate historical-average or explicitly selected forecast-driven replenishment guidance |

## Input limits and validation

- CSV uploads are limited to 10 MB per file.
- File names must end in `.csv`.
- Unsupported forecast horizons are rejected; allowed horizons are 7, 15 and 30 days.
- Sales data must contain `date,store,item,sales`.
- Inventory input must contain `store,item,on_hand,on_order,backorders,lead_time_days,review_period_days`.
- Invalid dates, non-finite or negative sales, missing identifiers, duplicate daily keys and irregular forecasting series are validated rather than silently treated as valid observations.
- Stock counts, supplier lead times and review periods must be explicitly supplied and pass validation.

## API request limits

The processing endpoints apply a configurable in-process per-client rate limit. Defaults are 120 requests per 60 seconds per client IP. Configure `DEMANDIQ_API_RATE_LIMIT_REQUESTS` and `DEMANDIQ_API_RATE_LIMIT_WINDOW_SECONDS` for local/single-process deployments. Responses over the limit return HTTP 429 with a `Retry-After` header.

This is defense in depth, not a distributed production abuse-control system: counters are local to one process and reset on restart. A production host or edge proxy must additionally enforce distributed rate limits, request-body size limits (including multipart overhead), connection/time limits and appropriate concurrency controls. Do not rely on CORS or this in-memory limiter as authentication.

## CORS

Development defaults allow `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:4173` and `http://127.0.0.1:4173`.

Set `DEMANDIQ_CORS_ORIGINS` to a comma-separated list of exact production origins. Do not use a wildcard for a credentialed production frontend.

## Authentication and production security boundary

All processing endpoints (`/api/v1/sales/validate`, `/api/v1/forecasts`, `/api/v1/inventory/template` and `/api/v1/inventory/recommendations`) require an HTTP Bearer token from a signed-in Supabase session. The API validates each token by calling the configured Supabase Auth `/auth/v1/user` endpoint with the project URL and publishable key. Invalid or missing tokens receive HTTP 401. Missing configuration or an unavailable Auth service fails closed with HTTP 503. The lightweight root and health endpoints remain public for service health checks.

Configure these backend environment variables:

- `SUPABASE_URL`: the existing Supabase project URL.
- `SUPABASE_PUBLISHABLE_KEY`: the project's publishable key (legacy anon key is also accepted by Supabase where applicable).
- `DEMANDIQ_CORS_ORIGINS`: comma-separated exact browser origins, for example `https://your-app.vercel.app`.

The backend does not need or use a Supabase service-role key. Never put one in the frontend, backend deployment environment for this authentication flow, or Git repository. The API remains stateless and does not directly read/write workspace records; Supabase RLS continues to protect browser-side workspace data.

CORS is a browser policy, not authentication. The in-process limiter is not distributed protection. A production host or edge proxy must additionally enforce distributed rate limits, total request-body size limits (including multipart overhead), connection/time limits and concurrency controls. The Render blueprint in the repository proposes a conservative per-process starting limit and has automatic deployment disabled.

## Tests

From the repository root:

```powershell
python -m pytest backend/tests -q
python -m pytest -q
```
