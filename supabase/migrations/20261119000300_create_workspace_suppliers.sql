-- DemandIQ Stage 5: workspace-scoped supplier directory.
create table if not exists public.suppliers (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null,
    owner_id uuid not null references auth.users (id) on delete cascade,
    supplier_name text not null,
    contact_person text,
    email text,
    phone text,
    default_lead_time_days integer,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint suppliers_workspace_owner_fk foreign key (workspace_id, owner_id)
        references public.workspaces (id, owner_id) on delete cascade,
    constraint suppliers_name_not_blank check (length(trim(supplier_name)) > 0),
    constraint suppliers_lead_time_check check (default_lead_time_days is null or default_lead_time_days > 0)
);
create index if not exists suppliers_workspace_name_idx
    on public.suppliers (workspace_id, supplier_name);
alter table public.suppliers enable row level security;
drop policy if exists "Users can manage their workspace suppliers" on public.suppliers;
create policy "Users can manage their workspace suppliers" on public.suppliers
    for all to authenticated
    using (owner_id = (select auth.uid()))
    with check (
        owner_id = (select auth.uid())
        and exists (
            select 1 from public.workspaces w
            where w.id = workspace_id and w.owner_id = (select auth.uid())
        )
    );
grant select, insert, update, delete on public.suppliers to authenticated;
