# DemandIQ Web Frontend

The React + TypeScript + Vite frontend is the authenticated DemandIQ product workspace and installable PWA.

## Requirements

- Node.js 20.19+ or 22.12+
- npm

## Run locally

From this directory:

```powershell
npm ci
npm run dev
```

Create `.env.local` from `.env.example` and configure the Supabase project URL, Supabase publishable key, and API base URL. Never put a Supabase secret/service-role key in a Vite environment variable.

## Main routes

- `/` — public product landing page
- `/login`, `/signup` — Supabase email authentication
- `/workspace` — protected overview
- `/workspace/sales` — sales CSV validation, import and history
- `/workspace/products` — product catalogue
- `/workspace/suppliers` — supplier reference directory
- `/workspace/forecasts` — demand forecasts
- `/workspace/inventory` — inventory planning
- `/workspace/analyses` — saved analysis history and exports

## Build and verify

```powershell
npm ci
npm run build
npm run preview
```

The production build is served by Vite preview (normally http://localhost:4173). The PWA service worker is registered only in production builds. Forecasting and inventory calculations require the FastAPI service and network access; the PWA does not provide full offline operation.

## Data and security boundaries

- Supabase Auth manages browser sessions; protected routes require a valid session.
- Supabase Row Level Security protects workspace data. Do not bypass RLS or expose service-role credentials in the browser.
- Sales source CSVs are stored in the private `sales-imports` bucket.
- The supplier directory is reference information only; it does not automatically fill inventory inputs or create purchase orders.
- The FastAPI processing API requires the current Supabase session access token on every sales-validation, forecasting and inventory-processing request. The frontend attaches the bearer token from the Supabase session; the backend validates it with Supabase Auth. The public health endpoint does not require a session. Production hosting must additionally enforce distributed rate limits and request/time limits.
- Store management and multi-user workspace membership are not implemented in this MVP.
