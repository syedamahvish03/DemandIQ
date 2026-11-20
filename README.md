# DemandIQ

**AI-Powered Retail Demand Forecasting & Inventory Intelligence**

DemandIQ is a retail-planning application that combines historical sales analysis, machine-learning demand forecasts and inventory replenishment calculations. It is designed as a portfolio MVP for small and medium retailers.

## Product status

The React + FastAPI product is implemented on `feature/product-architecture` and is ready for cloud deployment preparation. Stages 0–6 implementation and automated verification are complete. Public production launch still requires hosting-specific API access controls, abuse protection, a verified backup/restore plan and live deployment checks.

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
4. `20261120164007_add_foreign_key_supporting_indexes.sql`

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

## Evaluation evidence

The Store Item Demand Forecasting Challenge dataset was validated and profiled (913,000 rows, 500 store-item series, 2013–2017). On a recursive 30-day holdout, Random Forest pooled WAPE was 16.70% (7 days), 15.89% (15 days) and 15.07% (30 days). Across three rolling origins, pooled WAPE was 12.70%, 13.03% and 14.32% for the same horizons. Each evaluation run used a 200,000-row training subset; rolling-origin holdouts overlap, and three origins are limited evidence. These are offline benchmark results, not a production accuracy guarantee or automatic per-series model selection. Full methodology and limitations are in `docs/RELEASE_READINESS.md`.

## Security and release boundary

The React application uses Supabase Auth. Every FastAPI processing endpoint (sales validation, forecasting, inventory template and inventory recommendations) now requires a bearer access token and validates it with the configured Supabase Auth `/auth/v1/user` endpoint. The backend uses only the Supabase project URL and publishable key for this check; never configure a service-role key for this purpose. Missing/invalid tokens are rejected, and authentication-provider outages fail closed. The API remains stateless and does not read or write workspace records.

The processing endpoints also include a configurable per-process per-client rate limiter (default 120 requests per 60 seconds; the Render blueprint proposes 30 per 60 seconds). This is defense in depth only; production must additionally configure distributed edge rate limits, total request-body limits, execution-time limits and concurrency controls. CORS is restricted through the `DEMANDIQ_CORS_ORIGINS` environment variable and is not authentication.

Supabase Auth protects the frontend workspace. Workspace-owned tables use RLS, and the sales source-file bucket is private with user-folder policies. Keep all production secrets in the relevant hosting environment-variable dashboards; never commit them.

## Cloud deployment configuration

- Frontend: connect the GitHub `main` branch to Vercel with root directory `frontend`, install command `npm ci`, build command `npm run build`, and output directory `dist`. The Vercel SPA rewrite is in `frontend/vercel.json`.
- Backend: use the root-level `render.yaml` blueprint on Render. Automatic deployment is disabled in the blueprint; configure the Supabase URL, publishable key and exact Vercel origin in the Render environment before enabling service traffic.
- Python runtime: pinned to 3.11.11 in `.python-version`, matching the CI Python 3.11 line.
- Supabase: continue using the existing hosted project. GitHub contains migration source files, not the live database records or Storage objects.

These files prepare the hosting configuration only. No hosting service has been created or deployed by this change.

## Reproducible real-dataset evaluation

The Stage 6 evaluation runner accepts a real daily sales CSV with `date,store,item,sales` columns. It validates daily series continuity and duplicate keys, then exports recursive 7/15/30-day comparisons and rolling-origin results for Random Forest, seasonal-naive and moving-average baselines.

After obtaining the licensed Store Item Demand Forecasting Challenge training CSV (or another suitable dataset), run from the repository root:

```powershell
python scripts/run_release_evaluation.py --input path\\to\\train.csv
```

Outputs are written to `results/release_evaluation/` and are intentionally not committed with raw customer/dataset data. The script records dataset coverage, preprocessing checks, evaluation metadata and caveats. Actual measured results still need to be generated and reviewed before claiming model performance.

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
