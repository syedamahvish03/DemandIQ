# DemandIQ cloud deployment handoff

This guide prepares the existing React + FastAPI + Supabase application for a zero-cost initial deployment on Render. The Render Blueprint defines both application services and explicitly disables automatic deployment. Creating or deploying these services still requires the user's separate approval.

## 1. Approved architecture

- Render Static Site hosts the React/Vite frontend from `frontend/`.
- Render Free Web Service hosts the existing FastAPI backend from the repository root.
- The existing Supabase project continues to provide Auth, PostgreSQL, RLS and private Storage.
- GitHub stores source code and migrations; it does not store live database records or Storage object bytes.
- No production application component runs on the developer's laptop or a customer's phone.

The frontend and backend are separate Render services within one Render account. Supabase remains a separate cloud provider because it owns the existing database, authentication and file storage.

## 2. Render frontend service

The root-level `render.yaml` defines a static site with these settings:

| Setting | Value |
|---|---|
| Service name | `demandiq-frontend` |
| Service type | Static Site (`runtime: static`) |
| Branch | `main` |
| Root directory | `frontend` |
| Build command | `npm ci && npm run build` |
| Publish directory | `dist` |
| SPA fallback | Rewrite `/*` to `/index.html` |
| Automatic deploys | Disabled |

Set these build-time environment variables in Render after the service URLs are known:

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | HTTPS origin of the Render backend, e.g. `https://<api-service>.onrender.com` |
| `VITE_SUPABASE_URL` | Existing Supabase project URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Existing Supabase publishable key |

Vite embeds these values into the static frontend at build time. Changing them requires a new frontend build/deploy. Only the Supabase publishable key belongs in browser variables. Never use a Supabase secret/service-role key in a `VITE_*` variable.

## 3. Render backend service

The same root-level `render.yaml` defines the FastAPI service:

| Setting | Value |
|---|---|
| Service name | `demandiq-api` |
| Runtime | Python |
| Plan | Free |
| Branch | `main` |
| Build command | `pip install -r backend/requirements.txt` |
| Start command | `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT` |
| Health check | `/api/v1/health` |
| Automatic deploys | Disabled |

The root `.python-version` pins Python 3.11.11.

Set these backend environment variables in Render:

| Variable | Value |
|---|---|
| `SUPABASE_URL` | Existing Supabase project URL |
| `SUPABASE_PUBLISHABLE_KEY` | Same Supabase publishable key used by the frontend |
| `DEMANDIQ_CORS_ORIGINS` | Exact deployed Render frontend origin, e.g. `https://<frontend-service>.onrender.com` |
| `DEMANDIQ_API_RATE_LIMIT_REQUESTS` | `30` |
| `DEMANDIQ_API_RATE_LIMIT_WINDOW_SECONDS` | `60` |

Do not configure a service-role key for the API authentication flow. The backend validates a user's bearer access token through Supabase Auth `/auth/v1/user` using the publishable key. Missing/invalid tokens are rejected; if Auth is unavailable or misconfigured, processing fails closed.

## 4. Free-tier behavior and cost boundary

The frontend static site is free to host. The backend uses Render's Free web-service plan.

Important limitations:

- Render Free web services spin down after 15 minutes without inbound traffic. The next request can take about a minute to wake the service.
- Free services have limited CPU and memory and can be restarted by Render.
- Free services have ephemeral filesystems. Do not store customer uploads, database files or durable application data on the backend filesystem.
- Free service usage is subject to workspace monthly included bandwidth and build-pipeline limits. Exceeding included usage can lead to service suspension or additional charges depending on the usage and account settings.
- Supabase Free has its own quotas and inactivity behavior; database backups and restore guarantees are limited.

This is a zero-cost initial hosting target only while all provider usage remains within free allowances and no paid add-ons are selected. It is appropriate for deployment testing, learning and demonstrations, not a guarantee of uninterrupted commercial production availability. Monitor usage and billing settings. Do not enable paid services or add-ons without explicit approval.

## 5. Supabase Auth URL configuration — deferred approval required

After the final frontend URL is known, Supabase Auth URL configuration may need to be updated:

- Set the Site URL to the deployed frontend origin.
- Add the exact sign-up confirmation redirect URL `https://<frontend-domain>/login?confirmed=1` to the allowed redirect URLs.
- Keep localhost redirect URLs needed for local development.

**Do not make these Supabase changes as part of preparation.** Obtain the user's separate explicit approval first. Do not reapply migrations merely because hosting is being configured; the existing migrations were previously applied to the intended project.

## 6. Security and operational gates

Before public launch:

- Verify the exact Render frontend origin is configured in `DEMANDIQ_CORS_ORIGINS`.
- Confirm the backend has the correct Supabase URL and publishable key; never add a service-role key to frontend variables.
- Verify a signed-in user can run sales validation, forecasting and inventory processing.
- Verify missing, expired and invalid bearer tokens receive HTTP 401; verify Supabase Auth outages fail closed with HTTP 503.
- Configure appropriate distributed rate limits, total request-body limits, execution timeouts and concurrency controls. The in-process limiter is not a distributed control.
- Review logs for accidental credential or uploaded-data exposure.
- Complete cross-account database and private Storage access tests.
- Complete an independent backup/restore plan and drill.
- Test realistic CSV uploads and failed/partial import behavior.
- Review the free-tier cold-start experience and resource limits with actual workflows.

## 7. Current status and approval boundary

This branch contains the Render-only deployment configuration and documentation. It does not create Render services, enter environment variables, deploy the application, modify Supabase settings, apply migrations or change production data.

Both Render services have `autoDeployTrigger: off` in the Blueprint. Do not create/sync the Blueprint or trigger a deployment until the user separately approves that action. No Supabase configuration or data changes are authorized by approval of deployment preparation alone.
