-- DemandIQ Stage 3: workspace products, sales imports and sales records.
-- Run this migration in the Supabase SQL Editor after the previous workspace migration.

create table if not exists public.products (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null,
    owner_id uuid not null references auth.users (id) on delete cascade,
    item_code text not null,
    product_name text not null,
    category text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint products_workspace_owner_fk foreign key (workspace_id, owner_id)
        references public.workspaces (id, owner_id) on delete cascade,
    constraint products_item_code_not_blank check (length(trim(item_code)) > 0),
    constraint products_name_not_blank check (length(trim(product_name)) > 0),
    constraint products_workspace_item_unique unique (workspace_id, item_code),
    constraint products_id_workspace_unique unique (id, workspace_id)
);

create table if not exists public.sales_imports (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null,
    owner_id uuid not null references auth.users (id) on delete cascade,
    filename text not null,
    storage_path text,
    status text not null default 'processing',
    rows_received integer not null default 0,
    rows_imported integer not null default 0,
    rows_excluded integer not null default 0,
    validation_summary jsonb not null default '{}'::jsonb,
    error_message text,
    created_at timestamptz not null default now(),
    completed_at timestamptz,
    constraint sales_imports_workspace_owner_fk foreign key (workspace_id, owner_id)
        references public.workspaces (id, owner_id) on delete cascade,
    constraint sales_imports_status_check check (status in ('processing', 'completed', 'failed')),
    constraint sales_imports_counts_check check (
        rows_received >= 0 and rows_imported >= 0 and rows_excluded >= 0
    ),
    constraint sales_imports_id_workspace_owner_unique unique (id, workspace_id, owner_id)
);

create table if not exists public.sales_records (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null,
    owner_id uuid not null references auth.users (id) on delete cascade,
    import_id uuid not null,
    sales_date date not null,
    store_code text not null,
    item_code text not null,
    units_sold numeric(14, 3) not null,
    created_at timestamptz not null default now(),
    constraint sales_records_workspace_owner_fk foreign key (workspace_id, owner_id)
        references public.workspaces (id, owner_id) on delete cascade,
    constraint sales_records_import_fk foreign key (import_id, workspace_id, owner_id)
        references public.sales_imports (id, workspace_id, owner_id) on delete cascade,
    constraint sales_records_product_fk foreign key (workspace_id, item_code)
        references public.products (workspace_id, item_code) on delete restrict,
    constraint sales_records_units_nonnegative check (units_sold >= 0),
    constraint sales_records_daily_key_unique unique (workspace_id, sales_date, store_code, item_code)
);

create index if not exists products_workspace_created_idx
    on public.products (workspace_id, created_at desc);
create index if not exists sales_imports_workspace_created_idx
    on public.sales_imports (workspace_id, created_at desc);
create index if not exists sales_records_workspace_date_idx
    on public.sales_records (workspace_id, sales_date desc);
create index if not exists sales_records_workspace_item_date_idx
    on public.sales_records (workspace_id, item_code, sales_date desc);

alter table public.products enable row level security;
alter table public.sales_imports enable row level security;
alter table public.sales_records enable row level security;

drop policy if exists "Users can manage their workspace products" on public.products;
create policy "Users can manage their workspace products" on public.products
    for all to authenticated
    using (owner_id = (select auth.uid()))
    with check (
        owner_id = (select auth.uid())
        and exists (
            select 1 from public.workspaces w
            where w.id = workspace_id and w.owner_id = (select auth.uid())
        )
    );

drop policy if exists "Users can manage their sales imports" on public.sales_imports;
create policy "Users can manage their sales imports" on public.sales_imports
    for all to authenticated
    using (owner_id = (select auth.uid()))
    with check (
        owner_id = (select auth.uid())
        and exists (
            select 1 from public.workspaces w
            where w.id = workspace_id and w.owner_id = (select auth.uid())
        )
    );

drop policy if exists "Users can manage their sales records" on public.sales_records;
create policy "Users can manage their sales records" on public.sales_records
    for all to authenticated
    using (owner_id = (select auth.uid()))
    with check (
        owner_id = (select auth.uid())
        and exists (
            select 1 from public.workspaces w
            where w.id = workspace_id and w.owner_id = (select auth.uid())
        )
    );

grant select, insert, update, delete on public.products to authenticated;
grant select, insert, update, delete on public.sales_imports to authenticated;
grant select, insert, update, delete on public.sales_records to authenticated;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('sales-imports', 'sales-imports', false, 10485760, array['text/csv', 'application/vnd.ms-excel'])
on conflict (id) do update set
    public = false,
    file_size_limit = 10485760,
    allowed_mime_types = array['text/csv', 'application/vnd.ms-excel'];

drop policy if exists "Users can upload their own sales source files" on storage.objects;
create policy "Users can upload their own sales source files" on storage.objects
    for insert to authenticated
    with check (
        bucket_id = 'sales-imports'
        and (storage.foldername(name))[1] = (select auth.uid())::text
    );

drop policy if exists "Users can read their own sales source files" on storage.objects;
create policy "Users can read their own sales source files" on storage.objects
    for select to authenticated
    using (
        bucket_id = 'sales-imports'
        and (storage.foldername(name))[1] = (select auth.uid())::text
    );

drop policy if exists "Users can delete their own sales source files" on storage.objects;
create policy "Users can delete their own sales source files" on storage.objects
    for delete to authenticated
    using (
        bucket_id = 'sales-imports'
        and (storage.foldername(name))[1] = (select auth.uid())::text
    );
