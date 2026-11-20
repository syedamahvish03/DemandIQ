# DemandIQ

**AI-Powered Retail Demand Forecasting & Inventory Intelligence**

DemandIQ is a retail-planning application that combines historical sales analysis, machine-learning demand forecasts and inventory replenishment calculations. It is designed as a portfolio MVP for small and medium retailers.

## Product status

The React + FastAPI product is implemented on the `feature/product-architecture` branch. Stage 0–5 implementation is complete. Stage 6 hardening and release readiness is in progress. Production deployment and live verification are a separate final phase.

The original Streamlit application remains in the repository as the reference MVP.

## Current product capabilities

- Supabase email authentication and protected React workspace.
- Personal workspace records protected by Supabase Row Level Security (RLS).
- Sales CSV validation, preview, import history and private source-file storage.
- Workspace product catalogue and supplier reference directory.
- 7-, 15- and 30-day recursive Random Forest demand forecasts.
- Seasonal-naive and moving-average baselines, chronological evaluation and rolling-origin multi-horizon backtesting in the Python research workflow.
- Forecast-driven inventory planning using actual user-provided stock, incoming orders, backorders, supplier lead time and review period.
- Reorder alerts, calculation explanations, saved analyses and CSV exports.
- Installable PWA with a limited offline navigation fallback. Forecasting and inventory calculations still require the backend and are not available offline.

## Technology

- Frontend: React, TypeScript, Vite, React Router and CSS.
- API: Python, FastAPI, Pandas, NumPy and Scikit-learn.
- Research/reference app: Streamlit, Plotly and the shared Python domain modules.
- Data services: Supabase Auth, PostgreSQL, Row Level Security and private Supabase Storage.
- Automation: GitHub Actions.

## Repository structure

- `frontend/` — authenticated web application and PWA.
- `backend/` — FastAPI application and API tests.
- Root Python modules — data validation, EDA, forecasting and inventory logic shared with the Streamlit reference app.
- `supabase/migrations/` — ordered database and storage policies.
- `docs/` — product architecture, user guidance and release documentation.

## Run locally (Windows PowerShell)

### 1. Python environment and API

From the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

API health check: `http://127.0.0.1:8000/api/v1/health`.

### 2. Frontend

Open a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Create `frontend/.env.local` using `frontend/.env.example` as a guide. Configure the Supabase project URL and publishable/anon key. Never put a Supabase service-role key in frontend environment variables.

The Vite development app normally runs at `http://localhost:5173`.

### 3. Supabase database

Apply the migrations in order to the intended Supabase project:

1. `20261119000100_create_user_workspaces.sql`
2. `20261119000200_create_sales_import_foundation.sql`
3. `20261119000300_create_workspace_suppliers.sql`

Do not re-run migrations that are already applied unless the migration process explicitly requires it. Keep project secrets out of Git.

## Data inputs

### Historical sales CSV

Required columns: `date,store,item,sales`.

Each store-item series needs at least 15 consecutive daily observations for forecasting. The validation workflow reports invalid or excluded rows and blocks duplicate daily store-item keys from import.

### Inventory CSV

The inventory template contains:

- `store`, `item`: identifiers matching the sales history.
- `on_hand`: current physical stock.
- `on_order`: incoming units already ordered.
- `backorders`: units owed to customers.
- `lead_time_days`: supplier delivery time.
- `review_period_days`: time until the next stock review.

Inventory values are supplied by the retailer; DemandIQ does not infer actual stock or automatically place purchase orders. Supplier directory records are reference information and do not automatically populate inventory inputs.

## Modelling integrity and limitations

- Forecasting uses lagged sales, rolling means and calendar features.
- Production forecasts are recursive multi-step forecasts; one-step evaluation is not presented as equivalent to recursive forecast performance.
- The research workflow compares Random Forest with seasonal-naive and moving-average baselines using chronological and rolling-origin evaluation.
- No accuracy or business-impact percentage should be claimed without a documented real-dataset evaluation.
- Promotions, price changes, holidays, stockouts and future external events are not automatically modelled unless represented in the input features.
- Empirical error summaries are not formal prediction intervals.
- Inventory calculations are decision-support estimates, not purchase orders or guarantees against stockouts.

## Security and release boundary

The FastAPI processing endpoints now include a configurable per-process per-client rate limiter (default 120 requests per 60 seconds) and return HTTP 429 with `Retry-After` when exceeded. This is defense in depth only; production must also configure hosting/edge-level distributed rate limits, request-body and execution-time limits. The API remains stateless and does not verify Supabase access tokens. Do not expose it as a public unrestricted compute service.

Supabase Auth protects the frontend workspace. Workspace-owned tables use RLS, and the sales source-file bucket is private with user-folder policies.

The FastAPI forecast and inventory endpoints currently process uploaded CSVs statelessly and do not themselves verify a Supabase user token or persist user records. Before unrestricted public production exposure, Stage 6 must complete API abuse/rate-limit and deployment-access decisions. Do not interpret database RLS as authentication for the stateless API.

## Tests

From the repository root:

```powershell
python -m pytest -q
python -m py_compile app.py
```

For the frontend:

```powershell
cd frontend
npm ci
npm run build
```

GitHub Actions runs Python tests, the Streamlit syntax check and the frontend production build on pushes to the configured branches.

## Documentation

See `docs/PRODUCT_ARCHITECTURE.md` for the roadmap, `docs/RELEASE_READINESS.md` for the Stage 6 verification checklist and `backend/README.md` for API endpoint details.
