# DemandIQ Stage 6 — Release Readiness Checklist

This document tracks verification for the React + FastAPI product on `feature/product-architecture`. A feature is not considered verified merely because its code or database policy exists. Status below distinguishes repository/CI evidence, user-observed local checks and remaining production-only work.

## Current implementation snapshot

- Supabase Auth provides email/password sign-up, sign-in, session restoration and sign-out.
- Each account receives one personal workspace. Workspace membership, team roles and multi-workspace administration are not implemented in this MVP.
- RLS is enabled on `workspaces`, `analysis_runs`, `products`, `sales_imports`, `sales_records` and `suppliers`.
- The `sales-imports` Storage bucket is private. Source CSV objects are stored under a user/workspace/import path and Storage policies restrict access by the first user-ID path segment.
- FastAPI forecast, sales-validation and inventory endpoints are stateless. They do not read/write Supabase data and do not validate Supabase access tokens. The four processing endpoints have a configurable in-process per-client rate limiter (default 120 requests per 60 seconds). This is not distributed protection or API authentication. CORS is not authentication.
- Upload handlers enforce a 10 MB per-file read limit. Production infrastructure must also limit total multipart request bodies and resource consumption.
- The PWA has a manifest, install prompt and conservative navigation fallback. Forecasting and inventory operations require network/API access; full offline operation is not supported.
- Supplier records are a reference directory. They do not automatically populate inventory input CSVs or create purchase orders.
- Store management is not implemented.

## Verified evidence as of 20 November 2026

### Automated and local checks
- [x] GitHub Actions run #188 completed successfully on commit `0b5cc299f0796ac1ea78350df001749b67999dee`; a subsequent rate-limiter hardening change is awaiting its own CI run.
- [x] User ran the local full Python test suite: 131 passed, with one non-blocking Starlette/httpx deprecation warning.
- [x] User ran `python -m py_compile app.py scripts/run_release_evaluation.py` successfully.
- [x] User ran `npm run build` successfully. Vite emitted a non-blocking warning that the JavaScript bundle exceeded 500 kB (598.06 kB; 167.69 kB gzip).
- [x] User visually checked Dashboard, Sales, Products, Suppliers, Forecast, Inventory Planning and Saved Analyses at iPhone 16 Pro Max dimensions. No cutoff or horizontal scrolling was reported.
- [x] User signed out of Account B and directly opened workspace URLs. The tested protected routes redirected to Sign In.

### Account isolation and Storage
- [x] Account B started with empty product, sales-import, supplier and saved-analysis views.
- [x] Account B created `SECURITY-TEST-B-ONLY`; it did not appear in Account A's Products page after refresh.
- [x] Account B could not see Account A's import history, supplier records or saved analyses in the tested UI views.
- [x] Account B's Forecast and Inventory pages reported no imported workspace sales.
- [x] User inspected Supabase Storage and confirmed the `sales-imports` bucket is private and has authenticated-user INSERT, SELECT and DELETE policies scoped to the first folder segment matching `auth.uid()`.
- [x] User confirmed the Account A demo CSV object is present in the private bucket.
- [ ] A direct attempt by Account B to list/download/delete Account A's exact Storage object has not been performed. Policy inspection and UI isolation checks are not a substitute for this test.
- [ ] Direct cross-account read/update/delete attempts against every RLS table have not been individually tested. Do not describe the practical UI checks as exhaustive RLS penetration testing.

### Backup and recovery
- [x] Supabase Dashboard was checked; it states that managed project backups are not included on the current Free plan.
- [ ] No independent database export/backup and restore drill has been completed. This is a known release risk. Before production or real business data, establish scheduled independent backups and test restoration.

### Data Science evaluation
- [x] Reproducible evaluation runner added at `scripts/run_release_evaluation.py`.
- [x] User ran it against the Store Item Demand Forecasting Challenge training dataset (Kaggle), after adding the expected CSV headers.
- [x] Dataset profile: 913,000 valid rows, 0 excluded; 1,826 dates from 2013-01-01 to 2017-12-31; 10 stores; 50 items; 500 store-item series.
- [x] Recursive 30-day holdout evaluation completed for all 500 series. Random Forest pooled WAPE: 16.70% (7 days), 15.89% (15 days), 15.07% (30 days). Moving-average and seasonal-naive baselines were also evaluated and had higher pooled WAPE at each horizon.
- [x] Three-origin rolling-origin evaluation completed. Random Forest pooled WAPE: 12.70% (7 days), 13.03% (15 days), 14.32% (30 days); WAPE standard deviation across the three origins: 2.72, 1.86 and 1.36 percentage points respectively.
- [x] Per-series comparisons completed for 500 series × 3 horizons (1,500 comparisons); Random Forest was the selected lowest-mean-origin-WAPE model in 1,481 comparisons and moving average in 19.
- [x] Limitations are recorded: rolling-origin windows overlap (15-day spacing, 30-day holdout), only three origins were evaluated, model rankings are evaluation guidance rather than production auto-selection, and the dataset has no inventory/lead-time/promotion/future-event inputs.
- [ ] Preserve the generated result files locally or in the user's own research archive. Generated evaluation outputs are intentionally gitignored and were not committed.
- Note: although all 913,000 rows were validated and profiled, each evaluation run used a 200,000-row training subset as recorded in the evaluation metadata. Do not claim all 913,000 rows were used to fit each model.

## Stage 6 work items

### A. Automated regression and API validation
- [x] Existing Python unit and FastAPI tests pass in CI.
- [x] Frontend production build passes in CI and locally.
- [x] Full local Python test suite and syntax compilation were run after pulling the feature branch.
- [x] Core browser workflows were exercised by the user: import, catalogue, suppliers, forecast, inventory planning and saved analyses.
- [ ] Add or perform explicit malformed, empty, oversized and wrong-extension checks for every upload endpoint, including the combined inventory upload.
- [ ] Verify unexpected API errors do not expose stack traces, secrets or uploaded row contents.
- [ ] Run browser workflows on a local production preview, not only the development server, and capture any remaining edge cases.

### B. Supabase and storage isolation
- [x] Two separate test accounts used for practical UI-level isolation checks.
- [x] Private bucket configuration and owner-folder policies inspected.
- [ ] Attempt cross-account Storage list/download/delete against Account A's object while authenticated as Account B.
- [ ] Test direct cross-account database read/update/delete using record IDs for each RLS-protected table.
- [ ] Verify unauthenticated direct access to workspace tables and private Storage is denied.
- [ ] Verify actual local environment files, built assets and browser requests contain no service-role key or other secret. The tracked-file scan only verified the committed example configuration, not every local or deployed secret source.

### C. API exposure and abuse controls
- [x] Configurable in-process per-client rate limiting implemented (default 120 requests / 60 seconds; 429 plus `Retry-After`).
- [x] Rate-limit client storage is capped at 5,000 entries; expired entries are pruned and active limits are never cleared to make room. Regression tests cover full and expired buckets (new tests await CI).
- [x] API trust boundary documented: stateless endpoints do not access workspace records and do not validate Supabase access tokens.
- [x] Per-file upload reads are bounded at 10 MB.
- [ ] Before public deployment, choose and configure the API access strategy: authenticated API access or an explicitly accepted public compute endpoint protected by strong edge/hosting controls.
- [ ] Configure and verify distributed edge/hosting rate limits, total request-body limits (including multipart overhead), execution timeouts, concurrency limits and appropriate worker sizing.
- [ ] Apply exact production CORS origins.
- [ ] Verify request-size and processing limits under concurrent/repeated requests.
- [ ] Confirm API logs do not include uploaded CSV contents, credentials or personal data.
- Note: the in-process limiter is per worker, resets on restart and is not a substitute for edge controls. Do not expose the API as an unrestricted public compute service.

### D. Data integrity and recovery
- [ ] Exercise failed/partial sales imports and confirm no misleading completed import remains.
- [x] Duplicate daily store-item keys are included in validation blockers before import; a separate live UI test of a duplicate-file rejection remains to be captured.
- [ ] Verify failed imports do not leave inaccessible source files or misleading product/sales records.
- [ ] Establish an independent backup/export schedule and complete a restore drill before production use. Supabase Free currently provides no managed project backups.
- [ ] Confirm deletion behaviour and foreign-key cascades with test records.

### E. UI, accessibility and performance
- [x] User visually reviewed the desktop workspace pages after the shared-layout correction.
- [x] User visually reviewed all principal workspace pages at iPhone 16 Pro Max dimensions.
- [ ] Verify tablet widths.
- [ ] Check keyboard navigation, visible focus, labels, contrast, reduced-motion behaviour and screen-reader semantics.
- [ ] Test realistic large CSV uploads through the browser workflow within the 10 MB file and 100,000-row workspace-import limits. The 913,000-row research evaluation was a local CLI run, not a browser upload test.
- [ ] Verify empty, loading, success and error states for remaining edge cases.
- [ ] Review the Vite bundle-size warning and decide whether code splitting is warranted; this is a performance improvement, not currently a build failure.

### F. Documentation and release
- [x] Root, backend and Supabase setup/security documentation reviewed and updated for current architecture.
- [x] Tracked frontend environment example contains only a public Supabase URL and publishable-key placeholder; `.env*` files are ignored except `.env.example`.
- [x] Release checklist updated with the observed CI, local, browser, Storage and real-dataset evidence.
- [ ] Review any remaining documentation for outdated architecture and feature claims.
- [ ] Verify actual local environment files, production secret store, built assets and browser requests for secret exposure.
- [ ] Complete production configuration and hosting-specific deployment checklist.
- [ ] Obtain explicit approval before production deployment; deployment is a separate final phase after Stage 6.

## Release acceptance criteria

Stage 6 must not be marked complete until:
1. Automated tests and frontend production build pass.
2. Critical browser workflows pass on the local production preview.
3. Cross-account database and Storage isolation tests pass, including direct object access checks.
4. API production exposure and abuse controls have a documented, tested decision.
5. Failed import and data-recovery behaviour is understood and an independent backup/restore plan exists.
6. Real-dataset model-comparison evidence is recorded reproducibly.
7. Documentation and environment/secret checks are complete.

Production deployment and live end-to-end verification remain a separate final phase and require explicit user approval. No production deployment, merge to `main`, or Supabase data mutation is authorized by this checklist.
