-- Applied to the DemandIQ Supabase project as migration
-- 20261120164007_add_foreign_key_supporting_indexes.
-- Add child-side indexes for foreign keys identified by Supabase's performance advisor.
-- Additive and non-destructive: no application data is changed.

CREATE INDEX IF NOT EXISTS analysis_runs_workspace_owner_fk_idx
  ON public.analysis_runs (workspace_id, owner_id);

CREATE INDEX IF NOT EXISTS products_owner_fk_idx
  ON public.products (owner_id);
CREATE INDEX IF NOT EXISTS products_workspace_owner_fk_idx
  ON public.products (workspace_id, owner_id);

CREATE INDEX IF NOT EXISTS sales_imports_owner_fk_idx
  ON public.sales_imports (owner_id);
CREATE INDEX IF NOT EXISTS sales_imports_workspace_owner_fk_idx
  ON public.sales_imports (workspace_id, owner_id);

CREATE INDEX IF NOT EXISTS sales_records_import_workspace_owner_fk_idx
  ON public.sales_records (import_id, workspace_id, owner_id);
CREATE INDEX IF NOT EXISTS sales_records_owner_fk_idx
  ON public.sales_records (owner_id);
CREATE INDEX IF NOT EXISTS sales_records_workspace_owner_fk_idx
  ON public.sales_records (workspace_id, owner_id);

CREATE INDEX IF NOT EXISTS suppliers_owner_fk_idx
  ON public.suppliers (owner_id);
CREATE INDEX IF NOT EXISTS suppliers_workspace_owner_fk_idx
  ON public.suppliers (workspace_id, owner_id);
