# DemandIQ V2 — Product Architecture & Delivery Blueprint

## Product vision

DemandIQ is a multi-user retail demand intelligence platform. A retailer can create a private business workspace, import sales and product information, understand historical performance, forecast future product demand, and use those forecasts to support inventory and replenishment decisions.

The product must be understandable to a non-technical store owner. It must work well in a desktop browser and on Android phones. The first mobile deliverable is an installable Progressive Web App (PWA), sharing the same responsive application and account as desktop. A separate native Android application is not part of the first release.

## Product principles

1. Clear, guided workflows: explain what data is needed, why it is needed, and what the next action is.
2. Data honesty: distinguish retailer-provided facts, calculated values, model predictions, and illustrative examples.
3. Private by default: each user's business data is isolated and inaccessible to other tenants.
4. Preserve the validated MVP: reuse existing forecasting, validation, EDA and inventory logic after refactoring behind tested service interfaces.
5. Progressive complexity: basic workflows first; advanced settings and technical details remain optional.
6. Responsive and accessible: support laptop, tablet and Android mobile layouts, keyboard navigation, readable contrast and clear feedback.

## Product scope

### Public experience
- Marketing landing page explaining the value proposition and workflow.
- Features, how-it-works, pricing/readiness placeholder, help and contact sections.
- Sign up, sign in, password reset and email verification.
- Clear demo/sample-data experience that cannot be confused with a real connected business.

### Authenticated workspace
- Business onboarding: business name, type, country, currency, timezone and optional store locations.
- Overview: sales performance, demand signals, forecast summary and actionable alerts.
- Data centre: upload, map columns, preview, validate, import history and manage datasets.
- Product catalogue: SKU/product identifier, name, category, unit, optional cost/price and active status.
- Stores/locations: user-owned store records and location-specific product performance.
- Sales analytics: date range, product, category and store filters.
- Forecasting: configurable horizon, product/store selection, forecast chart, confidence/uncertainty explanation where supported, model/version and evaluation context.
- Inventory: actual on-hand, on-order, backorders, supplier lead time and review period supplied by the retailer; clearly labelled estimates where information is missing.
- Recommendations: reason, demand window, assumptions, calculation details and suggested next action.
- Reports: downloadable CSV initially; PDF reports after report design is established.
- Settings: business profile, users/members later, account, privacy and data export/deletion.

## Data input approach

Do not promise that the model can forecast from arbitrary unstructured information. The first supported input is guided CSV upload with a preview and column-mapping step. A sales dataset needs a date, product/SKU identifier and quantity sold; store/location is optional for a single-store retailer and required for multi-store analysis. Product catalogue and inventory inputs are separate guided imports. Manual entry and spreadsheet templates can support smaller retailers. POS/e-commerce integrations are future connectors, not assumed in the MVP.

The Kaggle starter dataset remains a development/demo dataset. It does not contain retailer identity, product names, stock on hand, purchase orders, backorders, costs or supplier lead times. Never infer these facts from Kaggle sales rows.

## Proposed architecture

### Frontend
- React + TypeScript + Vite.
- Tailwind CSS with a documented design-token system and reusable accessible components.
- React Router for public and authenticated routes.
- TanStack Query or an equivalent server-state layer for API calls, caching and loading/error states.
- A charting library for interactive analytics.
- PWA manifest, installability and service worker for app-like Android and desktop use. Cache only safe static assets and non-sensitive shell resources; do not cache private business API responses by default.

### Backend
- Python + FastAPI.
- Versioned REST API under /api/v1.
- Service layer for imports, analytics, forecasting, inventory and reports.
- Existing Python modules (data_loader.py, data_validation.py, eda.py, forecasting.py, inventory.py) are the initial domain logic to be inspected and adapted. Avoid a second implementation of these algorithms.
- Background jobs may be introduced for long-running forecasts/imports only when needed.

### Identity, database and files
- Supabase Auth for identity and session management.
- Supabase PostgreSQL for business and application records.
- Supabase Storage private buckets for uploaded source files and generated private reports.
- Row Level Security (RLS) on every tenant-owned table.
- Backend validates the authenticated user's identity and business membership for every protected operation. Never trust a client-supplied user_id or business_id without checking membership.
- Use least-privilege service credentials only on the server. Never expose service-role keys, database passwords or private secrets in frontend code or Git.
- Signed, short-lived file access where private downloads are required.

## Tenant and authorization model

Initial model:
- profiles: one row per authenticated user, keyed to auth.users.
- businesses: one or more business workspaces owned by users.
- business_members: membership and role mapping (owner, admin, analyst/viewer; team collaboration can be enabled after single-owner workflows).
- stores: belongs to a business.
- products: belongs to a business.
- sales_imports and sales_records: belong to a business; import metadata tracks source, mapping, validation and status.
- inventory_snapshots or inventory_items: belong to a business and optionally a store/product.
- suppliers: belong to a business.
- forecast_runs and forecast_values: belong to a business and reference the data/model version used.
- recommendations: belong to a business and reference forecast/inventory inputs.
- report_exports: belong to a business and a private storage object.

Security invariants:
1. Every tenant-owned record has a non-null business_id.
2. RLS policies authorize access only when auth.uid() is an active member of that business.
3. Inserts derive or validate business membership server-side; clients cannot assign themselves to another business.
4. Storage object paths include an opaque business scope and policies verify membership; path naming alone is not authorization.
5. Backend endpoints repeat authorization checks; frontend route guards are usability controls, not security boundaries.
6. Users cannot enumerate, read, modify or delete another business's records by changing IDs.
7. Audit important events such as sign-in, import, export, membership and destructive changes without logging secrets or raw sensitive file contents.
8. Provide account/business data export and deletion workflows with explicit confirmation and retention rules.

## Forecasting and inventory integrity

- Keep chronological evaluation; never use random train/test splitting for time series.
- Compare candidate models against simple baselines on the same evaluation window.
- Report MAE, RMSE, WAPE and bias with clear definitions and test-period dates.
- Do not claim a model is best unless supported by comparable validation results.
- Generate product/store forecasts only where the available history supports them; communicate insufficient history and cold-start limitations.
- Distinguish forecasts from actual sales and show forecast horizon and generated timestamp.
- Inventory calculations require verified inventory/supplier inputs or an explicitly labelled scenario. Missing stock is unknown, not zero.
- Recommendations explain inputs, formulas, assumptions and uncertainty. They are decision support, not automatic purchase orders.

## UX and visual direction

Premium, calm analytics SaaS. Use a restrained navy/charcoal foundation with a clear blue accent, high-contrast text, consistent spacing, readable typography, subtle borders and purposeful charts. Avoid visual clutter, excessive gradients, tiny labels and dashboard cards without actionable meaning.

Primary desktop navigation: Overview, Analytics, Forecasts, Inventory, Products, Data, Reports, Settings. On mobile, use a compact navigation pattern with a clear primary action and no horizontal overflow.

Every data workflow includes: purpose, accepted format, downloadable template, upload progress, column mapping, preview, validation summary, actionable correction guidance, import confirmation and import history.

Every screen must include thoughtful loading, empty, error, success and permission-denied states. Avoid dead buttons and unexplained technical errors.

## Delivery phases

### Phase 0 — Foundation and audit (current)
- Keep existing main branch and Streamlit MVP intact.
- Work on feature/product-v2-foundation.
- Inspect current Python modules, tests, data assumptions and dependency constraints.
- Confirm the API/domain contracts and data model before migrating algorithms.
- Produce route map, schema/RLS design, design tokens and acceptance criteria.

### Phase 1 — Product design system and public frontend
- Add frontend application without deleting app.py.
- Build responsive landing page, shared layout, components and design tokens.
- Build sign-up/sign-in/reset screens with real Supabase Auth integration only after environment configuration is ready.
- Add route guards and accessible feedback states.

### Phase 2 — Secure business onboarding and tenant data
- Implement profiles, businesses, memberships and RLS.
- Add onboarding and business switcher if multiple workspaces are supported.
- Add secure product/store catalogue and guided CSV import.
- Verify cross-tenant isolation with automated tests before storing real user data.

### Phase 3 — Backend and analytics
- Add FastAPI with versioned endpoints and service/repository boundaries.
- Refactor and reuse existing Python domain modules.
- Persist import metadata, normalized sales and product/store data.
- Connect frontend analytics to authenticated APIs.

### Phase 4 — Forecasting and inventory product workflows
- Integrate forecast runs, model evaluation, inventory inputs and recommendations.
- Explain forecasts and recommendations in retailer-friendly language.
- Add report exports and private download access.

### Phase 5 — PWA and product refinement
- Installable Android/desktop PWA, responsive QA, performance, accessibility, security review, backups and operational monitoring.
- Native Android app only if a validated need remains after the PWA.

### Phase 6 — Final QA and deployment
- End-to-end, security, tenant-isolation, usability and regression testing.
- Production configuration, deployment, monitoring and release documentation.
- This phase is explicitly deferred until the owner requests it.

## Non-goals for the first product release

- Do not claim arbitrary natural-language input can replace structured sales/inventory data.
- Do not implement payment/billing before core product value and security are established.
- Do not build a separate native Android codebase before validating the PWA.
- Do not add external POS integrations until the import/data model is stable.
- Do not delete or rewrite the working Streamlit MVP during the initial frontend foundation work.

## Definition of done for a first usable multi-user release

A new retailer can register, verify and sign in; create a business; import and validate sales data; manage products and stores; view analytics; generate supported forecasts; enter real inventory information; understand recommendations; export their own reports; install/use the responsive PWA on Android and laptop; and cannot access another business's data. Security and tenant-isolation tests must pass before real multi-user launch.
