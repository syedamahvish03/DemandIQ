# DemandIQ Stage 6 — Release Readiness Checklist

This document tracks verification work for the current React + FastAPI product on `feature/product-architecture`. A feature is not considered verified merely because its code or database policy exists.

## Current implementation snapshot

- Supabase Auth provides email/password sign-up, sign-in, session restoration and sign-out.
- Each account receives one personal workspace. Workspace membership, team roles and multi-workspace administration are not implemented in this MVP.
- RLS is enabled on `workspaces`, `analysis_runs`, `products`, `sales_imports`, `sales_records` and `suppliers`.
- The `sales-imports` Storage bucket is private. Source CSV objects are stored under a user/workspace/import path and Storage policies restrict access by the first user-ID path segment.
- FastAPI forecast, sales-validation and inventory endpoints are stateless. They do not read/write Supabase data and currently do not validate Supabase access tokens or apply application-level rate limits. CORS is not authentication.
- The PWA has a manifest, install prompt and conservative navigation fallback. Forecasting and inventory operations require network/API access; full offline operation is not supported.
- Supplier records are a reference directory. They do not automatically populate inventory input CSVs or create purchase orders.
- Store management is not implemented.

## Existing automated verification

GitHub Actions currently runs:
- Python unit and API tests via `python -m pytest -q`.
- Streamlit syntax compilation.
- Frontend dependency installation and Vite production build.

Backend tests already cover health checks, forecasting, CSV validation, upload size limits, invalid encodings, unsupported horizons, inventory templates and recommendation validation. Forecasting tests cover chronological and recursive multi-horizon evaluation, rolling-origin evaluation, leakage safeguards and invalid time-series inputs.

A passing CI run verifies the covered automated checks only. It does not prove Supabase RLS behaviour, production deployment, cross-account isolation or browser workflows.

## Stage 6 work items

### A. Automated regression and API validation
- [x] Existing Python unit and FastAPI tests pass in CI.
- [x] Frontend production build passes in CI after the visual refresh.
- [ ] Run the full test suite locally after pulling the latest branch.
- [ ] Exercise every user workflow in the browser after the UI refresh.
- [ ] Verify API validation for malformed, empty, oversized and wrong-extension files on every upload endpoint.
- [ ] Verify unexpected API errors do not expose stack traces, secrets or uploaded row contents.

### B. Supabase and storage isolation
- [ ] Create/use two separate test accounts.
- [ ] Confirm each account sees only its own workspace, products, imports, sales rows, suppliers and saved analyses.
- [ ] Attempt cross-account read, update and delete operations using the other account's record IDs; each must be denied or return no rows.
- [ ] Verify private Storage objects cannot be listed, downloaded or deleted by the other account.
- [ ] Verify unauthenticated users cannot access workspace tables or private Storage.
- [ ] Confirm no service-role key or other secret is present in frontend source, built assets, committed files or browser requests.

### C. API exposure and abuse controls
- [x] Add configurable in-process rate limiting to CPU/memory-heavy API routes, with a 429 response and `Retry-After` header.
- [ ] Decide how production FastAPI endpoints will be protected against anonymous resource abuse (for example, hosting-level rate limits and request-size/time limits, and/or authenticated API access).
- [ ] Apply exact production CORS origins; never treat CORS as an authentication control.
- [ ] Verify request-size limits and practical processing limits under concurrent or repeated requests.
- [ ] Confirm API logs do not include uploaded CSV contents, credentials or personal data.

### D. Data integrity and recovery
- [ ] Test failed/partial sales imports and confirm no misleading completed import remains.
- [ ] Verify duplicate daily store-item keys are blocked before import.
- [ ] Verify failed imports do not leave inaccessible source files or misleading product/sales records.
- [ ] Review Supabase backup/restore options and document a recovery approach before production use.
- [ ] Confirm deletion behaviour and foreign-key cascades are understood.

### E. Data Science evidence
- [x] Add a reproducible CLI runner for real-dataset recursive multi-horizon and rolling-origin evaluation (`scripts/run_release_evaluation.py`).
- [ ] Run the evaluation runner on the selected real retail dataset and review the exported results.
- [ ] Record dataset source, row count, date coverage, number of store-item series and preprocessing decisions.
- [ ] Report Random Forest against seasonal-naive and moving-average baselines at 7-, 15- and 30-day horizons.
- [ ] Include MAE, RMSE, WAPE and bias, plus rolling-origin variability.
- [ ] Explain limitations and report results as measured; do not promise a model win or invent accuracy/impact values.
- [ ] Preserve reproducible evaluation commands and result tables for the report.

### F. UI, accessibility and performance
- [ ] Verify dashboard, imports, catalogue, suppliers, forecasts, inventory and saved analyses at desktop, tablet and mobile widths.
- [ ] Check keyboard navigation, visible focus, labels, contrast, reduced-motion behaviour and screen-reader semantics.
- [ ] Test larger realistic CSV files within the documented 10 MB and 100,000-row limits.
- [ ] Verify empty, loading, success and error states for all workflows.

### G. Documentation and release
- [x] Update root and backend setup/security documentation to reflect the current product.
- [ ] Review all remaining docs for outdated architecture and feature claims.
- [ ] Complete environment-variable and secret review.
- [ ] Complete production configuration and deployment checklist.
- [ ] Obtain explicit approval before production deployment; deployment is a separate final phase after Stage 6.

## Release acceptance criteria

Stage 6 can be marked complete only when:
1. Automated tests and frontend production build pass.
2. All critical browser workflows pass on the local production preview.
3. Cross-account database and Storage isolation tests pass with two accounts.
4. API production exposure and abuse controls have a documented, tested decision.
5. Failed import and data-recovery behaviour is understood and tested.
6. Real-dataset model-comparison evidence is recorded reproducibly.
7. Documentation and environment/secret checks are complete.

Production deployment and live end-to-end verification remain a separate final phase and require explicit user approval.
