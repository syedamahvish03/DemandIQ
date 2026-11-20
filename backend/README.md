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

## CORS

Development defaults allow `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:4173` and `http://127.0.0.1:4173`.

Set `DEMANDIQ_CORS_ORIGINS` to a comma-separated list of exact production origins. Do not use a wildcard for a credentialed production frontend.

## Authentication and production security boundary

The frontend uses Supabase Auth. Supabase RLS protects workspace database records and private source-file storage. The FastAPI endpoints described above are currently stateless and do not validate Supabase access tokens; they do not directly read or write private workspace records.

Before exposing the API publicly in production, Stage 6 must decide and verify appropriate abuse controls (including request/rate limits and hosting-level protections) and document the trust boundary. CORS is a browser policy, not API authentication. Never place Supabase service-role credentials in the frontend or commit secrets.

## Tests

From the repository root:

```powershell
python -m pytest backend/tests -q
python -m pytest -q
```
