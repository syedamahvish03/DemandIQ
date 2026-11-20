# Supabase database setup

DemandIQ uses Supabase Auth for identity. The SQL migration in `migrations/` adds
one personal workspace per authenticated user and a private history table for
saved forecast and inventory results.

## Apply the migration

1. Open the DemandIQ project in the Supabase Dashboard.
2. Open **SQL Editor**.
3. Choose **New query**.
4. Copy the complete contents of
   `migrations/20261119000100_create_user_workspaces.sql` from this repository.
5. Paste the SQL into the editor and click **Run**.
6. Confirm the query completes without an error.
7. Repeat the same process with `migrations/20261119000200_create_sales_import_foundation.sql`.
8. Confirm both migrations complete successfully before testing Sales & imports or Product catalogue.
9. Apply `migrations/20261119000300_create_workspace_suppliers.sql` to enable the supplier directory.

The migrations:
- create `public.workspaces` and `public.analysis_runs`;
- backfill a personal workspace for existing Auth users and create one for future signups;
- create workspace-scoped `public.products`, `public.sales_imports`, and `public.sales_records`;
- create workspace-scoped `public.suppliers` with owner-scoped RLS;
- enforce owner-scoped Row Level Security and foreign-key relationships;
- create a private `sales-imports` Storage bucket with owner-folder policies;
- preserve uploaded CSV source files privately and store import counts and validation metadata.

## Security model

The browser uses only the Supabase publishable key. Do not put a Supabase
secret/service-role key in the frontend, local Vite environment variables, or
Git. Authenticated users can read/update their own workspace and create, read,
or delete their own analysis runs. The composite foreign key prevents an
analysis run from being attached to another user's workspace.

## Current implementation boundary

The SQL files must be applied manually in the Supabase SQL Editor; pushing the
migration files to GitHub does not execute them. The frontend import and
catalogue screens require the second migration. Apply all three migrations in
filename order, then test the workflows with a non-production/sample CSV first.
Original source files are private and accessible only to their owning account.
