# DemandIQ cloud deployment handoff

This guide prepares the existing React + FastAPI + Supabase application for deployment. The configuration files in this branch do not create hosting services or deploy the application. The Render Blueprint explicitly sets `autoDeploy: false`.

## 1. Architecture

- Vercel hosts the React/Vite frontend from `frontend/`.
- Render hosts the FastAPI service from the repository root.
- The existing Supabase project continues to provide Auth, PostgreSQL, RLS and private Storage.
- GitHub stores source code and migrations; it does not store live database records or Storage object bytes.

## 2. Vercel frontend settings

Connect `syedamahvish03/DemandIQ` and select production branch `main` when you are ready to create the Vercel project.

| Setting | Value |
|---|---|
| Root directory | `frontend` |
| Framework preset | Vite |
| Install command | `npm ci` |
| Build command | `npm run build` |
| Output directory | `dist` |

Set these Vercel environment variables for the Production environment (and Preview only if you intentionally configure preview API access):

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | Render service HTTPS origin, e.g. `https://<service>.onrender.com` |
| `VITE_SUPABASE_URL` | Existing Supabase project URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Existing Supabase publishable key |

The SPA route fallback is committed at `frontend/vercel.json`. Only the Supabase publishable key belongs in browser variables. Never use a Supabase secret/service-role key in a `VITE_*` variable.

## 3. Render backend settings

Use the root-level `render.yaml` Blueprint when creating the Render service. It configures:

- Python runtime pinned by root `.python-version` (3.11.11).
- Build: `pip install -r backend/requirements.txt`.
- Start: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`.
- Health check: `/api/v1/health`.
- Automatic deployment disabled until deliberately enabled.

Set the following Render environment variables before starting the service:

| Variable | Value |
|---|---|
| `SUPABASE_URL` | Existing Supabase project URL |
| `SUPABASE_PUBLISHABLE_KEY` | Same Supabase publishable key used by the frontend |
| `DEMANDIQ_CORS_ORIGINS` | Exact deployed Vercel origin, e.g. `https://<project>.vercel.app` |
| `DEMANDIQ_API_RATE_LIMIT_REQUESTS` | Blueprint starts at `30` |
| `DEMANDIQ_API_RATE_LIMIT_WINDOW_SECONDS` | Blueprint starts at `60` |

Do not configure a service-role key for the API authentication flow. The backend validates a user's bearer access token through Supabase Auth `/auth/v1/user` using the publishable key. Missing/invalid tokens are rejected; if Auth is unavailable or misconfigured, processing fails closed.

## 4. Supabase Auth URL configuration

After the final frontend domain is known, update the existing Supabase project's Auth URL configuration:

- Set the Site URL to the deployed frontend origin.
- Add the exact sign-up confirmation redirect URL `https://<frontend-domain>/login?confirmed=1` to the allowed redirect URLs.
- Keep localhost redirect URLs needed for local development.
- Do not apply migrations again just because hosting is being configured. All four existing migrations were previously applied to the intended project.

## 5. Security and operational gates

Before public launch:

- Verify the exact Vercel origin is configured in `DEMANDIQ_CORS_ORIGINS`.
- Confirm the backend has the correct Supabase URL and publishable key; never add a service-role key to frontend variables.
- Verify a signed-in user can run sales validation, forecasting and inventory processing.
- Verify missing, expired and invalid bearer tokens receive HTTP 401; verify Supabase Auth outages fail closed with HTTP 503.
- Configure hosting/edge-level distributed rate limits, total multipart request-body limits, execution timeouts and concurrency controls. The in-process limiter is not a distributed control.
- Review logs for accidental credential or uploaded-data exposure.
- Complete a backup/restore drill and the remaining cross-account database/Storage checks documented in `RELEASE_READINESS.md`.

## 6. Current status

This branch contains deployment configuration and API authentication changes for review and CI testing. No Vercel project or Render service has been created by these commits, no production environment variables have been entered, no Supabase settings or data have been changed, and no deployment has been performed. Merge to `main` only after reviewing the branch and its passing checks; merging is not itself a deployment instruction unless hosting auto-deploy is later enabled.
