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

The migration:
- creates `public.workspaces` and `public.analysis_runs`;
- backfills a personal workspace for existing Auth users;
- creates a personal workspace automatically for future signups;
- enables Row Level Security and owner-scoped policies;
- stores analysis results as JSONB, not original uploaded CSV files.

## Security model

The browser uses only the Supabase publishable key. Do not put a Supabase
secret/service-role key in the frontend, local Vite environment variables, or
Git. Authenticated users can read/update their own workspace and create, read,
or delete their own analysis runs. The composite foreign key prevents an
analysis run from being attached to another user's workspace.

## Current implementation boundary

This migration creates the database foundation. It does not, by itself, add
save/history UI or make the frontend write analysis results. Those application
changes are a separate step and should be tested after this migration has been
applied to the Supabase project.
