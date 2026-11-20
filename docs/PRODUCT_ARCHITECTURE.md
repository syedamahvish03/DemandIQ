# DemandIQ Product Architecture

> **Implementation status (Stage 6 review, 20 November 2026):** This document records both the product direction and the current release boundary. The delivered MVP uses Supabase Auth with one personal workspace per account; workspace team membership and roles, store management, guided onboarding, password recovery and native mobile apps are not implemented. The frontend uses custom CSS rather than Tailwind. Sales imports retain original CSVs in a private Supabase Storage bucket. The supplier directory is a reference list and is not automatically connected to inventory inputs or purchase orders. The FastAPI processing endpoints are stateless and currently do not validate Supabase access tokens or apply application-level rate limits. The PWA supports installation and a limited navigation fallback, not offline forecasting. See [the Stage 6 release-readiness checklist](RELEASE_READINESS.md) and the root README for the verified current state.

## 1. Product vision

DemandIQ is a multi-user retail demand forecasting and inventory intelligence web application. It helps an individual retailer or retail team understand product performance, explore historical sales, estimate future demand, and make evidence-based replenishment decisions.

The product must be understandable to non-technical store owners. Users should be guided through setup, data import, validation, insights, forecasts, and inventory planning without needing to know Python, SQL, or machine-learning terminology.

## 2. Product access and device strategy

The first complete product target is a responsive Progressive Web App (PWA):
- Public marketing website and product information.
- Sign-up, sign-in, password recovery, and protected application workspace.
- Responsive layouts for laptop/desktop, Android phones, and tablets.
- Installable from supported mobile and desktop browsers using the browser's install flow.
- One account and cloud-backed workspace, so the same authorized data is available across a user's devices.

A PWA is the first release target, not a claim that a native Android APK has already been built. A native Android application can be considered later if user needs justify it.

## 3. Proposed technology architecture

### Frontend
- React + Vite + TypeScript.
- Tailwind CSS and an accessible component system.
- Responsive charts and tables.
- PWA manifest and service worker, introduced after core routing and authentication are stable.

### Backend
- Python + FastAPI.
- Reuse and adapt the existing DemandIQ Python domain modules: data_loader.py, data_validation.py, eda.py, forecasting.py, and inventory.py.
- API endpoints validate identity, workspace ownership, inputs, and permissions before accessing data.
- Long-running imports/forecast jobs can move to a background worker if measured needs require it; do not add infrastructure prematurely.

### Managed services
- Supabase Auth for identity and sessions.
- Supabase PostgreSQL for workspace-scoped business data.
- Supabase Storage for private source files and generated reports.
- Row Level Security (RLS) on every tenant-owned table, backed by server-side authorization checks.

The existing Streamlit application remains a working reference/MVP during migration. It should not be removed until the new application covers its required workflows and the user explicitly approves retirement.

## 4. Main user journey

1. Visitor opens the public DemandIQ website.
2. Visitor reviews features and creates an account or signs in.
3. New user creates a workspace for their store/business and sets basic preferences: business name, timezone, currency, and units where relevant.
4. Guided setup explains which data is useful and offers a clearly labelled sample workspace for exploration.
5. User imports sales data using a template or column-mapping wizard.
6. DemandIQ validates the file and shows a preview, row counts, errors, and warnings before import.
7. User can add or import product catalogue and inventory information separately.
8. User explores sales analytics and generates forecasts.
9. Inventory recommendations are shown only when the required stock and replenishment inputs exist; otherwise the app labels assumptions and explains what is missing.
10. User can save, revisit, and export reports from their own workspace.

## 5. Core application areas

- Overview: business KPIs, data status, recent activity, and priority insights.
- Products: product catalogue, identifiers/SKU, category, unit, and product-level performance.
- Sales: imports, historical sales, store/product filters, and trend exploration.
- Forecasts: configurable forecast horizon, model/backtest information, uncertainty where supportable, and product/store drill-down.
- Inventory: stock snapshots, inventory position, lead time, safety stock assumptions, reorder point, and suggested order quantity.
- Suppliers and purchasing: optional supplier records and purchase-order workflow in a later iteration.
- Reports: saved and downloadable summaries.
- Data management: imports, mapping, validation results, and source-file history.
- Workspace settings: business profile, members/roles, preferences, and account settings.

## 6. Tenant isolation and security requirements

A workspace is the tenant boundary. A user may own or be a member of one or more workspaces. Every business record must be associated with a workspace.

Required safeguards:
- Never trust a workspace ID supplied by the browser by itself. Verify the authenticated user is an active member of that workspace on every server request.
- Enable and test Supabase RLS for all workspace-owned database tables. Policies must check membership and role.
- Use the Supabase service-role key only in trusted server environments. Never expose it in frontend code, browser bundles, logs, or public repository files.
- Use private Storage buckets and workspace-scoped storage paths with authorization policies or short-lived signed URLs.
- Validate file type, size, encoding, required columns, dates, numeric values, and row counts. Treat uploaded files as untrusted input.
- Keep secrets in environment variables and deployment secret stores; commit only .env.example placeholders.
- Apply least-privilege roles: workspace owner, admin, member, viewer, as appropriate.
- Avoid leaking one workspace's records through search, exports, errors, caches, logs, or generated reports.
- Add audit events for sensitive actions such as membership changes, imports, and exports.
- Use secure session handling, rate limits on authentication-sensitive endpoints, and clear account recovery flows.
- Do not claim security is complete until isolation tests have attempted cross-workspace reads and writes and verified they are denied.

## 7. Initial data model (logical, not yet migrated)

- profiles: application profile linked to Supabase Auth user.
- workspaces: one retail business/store workspace, with owner and preferences.
- workspace_members: user-to-workspace membership and role.
- products: workspace-scoped product catalogue and SKU.
- stores: optional locations belonging to a workspace.
- sales_records: dated product/store sales quantities and optional revenue fields.
- inventory_snapshots: dated on-hand and reserved quantities, when supplied by the retailer.
- suppliers: optional supplier details and lead-time information.
- forecast_runs: workspace, filters, horizon, model/version, training cutoff, and run metadata.
- forecast_values: product/store/date predictions and supported intervals.
- inventory_recommendations: inputs, assumptions, calculations, recommendation, and explanation.
- imports: file metadata, mapping, validation summary, and import status.
- audit_events: security-relevant activity metadata.

All tenant-owned tables must include workspace_id and have appropriate foreign keys and RLS. This is a design proposal; schema creation and migration require a separate reviewed implementation step.

## 8. Data integrity and honest intelligence

The starter Kaggle Store Item Demand dataset provides historical date, store, item, and sales fields. It does not provide actual on-hand inventory, purchase orders, supplier records, or lead times.

Therefore:
- Sales-only users can access sales analytics and demand forecasts.
- Inventory recommendations require real user-provided inventory/replenishment inputs or must be explicitly labelled as a scenario using assumptions.
- Never present synthetic demo values or assumed stock as a retailer's actual inventory.
- Preserve source data and import provenance; do not silently overwrite records.
- Show data freshness, missing fields, and limitations alongside insights.
- Forecast quality must be evaluated with chronological validation; no accuracy promise without evidence.

## 9. Incremental delivery plan

### Stage 0 — Architecture and UX foundation
- Confirm product scope, user journeys, tenant boundary, logical schema, and security requirements.
- Establish a separate feature branch and preserve the existing MVP.

### Stage 1 — Product shell and design system
- Create frontend app, design tokens, responsive navigation, landing page, and reusable components.
- Build accessible layouts for mobile and desktop.

### Stage 2 — Authentication and onboarding
- Connect Supabase Auth.
- Add sign-up, sign-in, recovery, workspace creation, and protected routes.
- Add authorization and initial RLS policies before storing customer data.

### Stage 3 — Workspace data foundation
- Add schema migrations, private storage, product catalogue, sales import wizard, validation preview, and import history.

### Stage 4 — Intelligence API integration
- Expose existing analytics, forecasting, and inventory domain logic through FastAPI.
- Add workspace-scoped APIs and product/store drill-downs.

### Stage 5 — Advanced product features
- Add inventory alerts and explainable replenishment insights.
- Add a workspace-scoped supplier directory for supplier contacts and default lead-time references.
- Improve saved analysis/report workflows and CSV exports.
- Add PWA manifest, installation prompt, and a conservative offline navigation fallback.

### Stage 6 — Hardening and release readiness
- Cross-tenant security tests, functional tests, accessibility, performance, backup/recovery review, documentation, and release preparation.
- Verify production environment configuration and deployment prerequisites.

### Final release phase — Production deployment
- Deploy the frontend and FastAPI backend to selected hosting providers.
- Configure production environment variables, Supabase URL/keys, CORS, HTTPS, and allowed origins.
- Apply reviewed Supabase migrations to the production project.
- Verify authentication, sales imports, forecasts, inventory plans, supplier records, and saved analyses against the live services.
- Deployment is separate from the numbered Stage 0–6 development roadmap and requires the user's approval.

## 10. Non-goals for the first product release

- Native Android app before validating the PWA.
- Billing/subscriptions and complex SaaS administration.
- Direct integrations with every POS/e-commerce provider.
- Unverified AI-generated business claims.
- Complex microservices or orchestration before the product needs them.

## 11. Migration and repository safety

- Keep all work within syedamahvish03/DemandIQ.
- Develop new product architecture on feature/product-architecture.
- Do not modify any other repository.
- Do not delete or replace the existing Streamlit MVP or tested Python modules during initial frontend/backend scaffolding.
- Prefer small, reviewable commits and run focused checks after each implementation stage.
