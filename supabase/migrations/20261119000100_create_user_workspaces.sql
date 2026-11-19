-- DemandIQ: personal workspaces and saved analysis runs.
-- Apply this migration in the Supabase SQL Editor for the DemandIQ project.
-- No uploaded CSV files or authentication secrets are stored by this schema.

create table if not exists public.workspaces (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null unique references auth.users (id) on delete cascade,
    name text not null default 'My workspace',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint workspaces_id_owner_id_unique unique (id, owner_id),
    constraint workspaces_name_not_blank check (length(trim(name)) > 0)
);

create table if not exists public.analysis_runs (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null,
    owner_id uuid not null references auth.users (id) on delete cascade,
    analysis_type text not null,
    title text not null,
    input_filename text,
    horizon_days integer,
    summary jsonb not null default '{}'::jsonb,
    result jsonb not null,
    created_at timestamptz not null default now(),
    constraint analysis_runs_type_check
        check (analysis_type in ('forecast', 'inventory')),
    constraint analysis_runs_title_not_blank
        check (length(trim(title)) > 0),
    constraint analysis_runs_horizon_check
        check (horizon_days is null or horizon_days in (7, 15, 30)),
    constraint analysis_runs_workspace_owner_fk
        foreign key (workspace_id, owner_id)
        references public.workspaces (id, owner_id)
        on delete cascade
);

create index if not exists analysis_runs_owner_created_idx
    on public.analysis_runs (owner_id, created_at desc);

create index if not exists analysis_runs_workspace_created_idx
    on public.analysis_runs (workspace_id, created_at desc);

alter table public.workspaces enable row level security;
alter table public.analysis_runs enable row level security;

drop policy if exists "Users can view their own workspace" on public.workspaces;
create policy "Users can view their own workspace"
    on public.workspaces for select
    to authenticated
    using (owner_id = (select auth.uid()));

drop policy if exists "Users can update their own workspace" on public.workspaces;
create policy "Users can update their own workspace"
    on public.workspaces for update
    to authenticated
    using (owner_id = (select auth.uid()))
    with check (owner_id = (select auth.uid()));

drop policy if exists "Users can view their own analysis runs" on public.analysis_runs;
create policy "Users can view their own analysis runs"
    on public.analysis_runs for select
    to authenticated
    using (owner_id = (select auth.uid()));

drop policy if exists "Users can create their own analysis runs" on public.analysis_runs;
create policy "Users can create their own analysis runs"
    on public.analysis_runs for insert
    to authenticated
    with check (
        owner_id = (select auth.uid())
        and exists (
            select 1
            from public.workspaces w
            where w.id = workspace_id
              and w.owner_id = (select auth.uid())
        )
    );

drop policy if exists "Users can delete their own analysis runs" on public.analysis_runs;
create policy "Users can delete their own analysis runs"
    on public.analysis_runs for delete
    to authenticated
    using (owner_id = (select auth.uid()));

-- Create one personal workspace for existing accounts. New accounts receive one
-- through the auth.users trigger below.
insert into public.workspaces (owner_id)
select id
from auth.users
on conflict (owner_id) do nothing;

create or replace function public.create_demandiq_workspace_for_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    insert into public.workspaces (owner_id)
    values (new.id)
    on conflict (owner_id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created_create_demandiq_workspace on auth.users;
create trigger on_auth_user_created_create_demandiq_workspace
    after insert on auth.users
    for each row execute procedure public.create_demandiq_workspace_for_new_user();

grant select, update on public.workspaces to authenticated;
grant select, insert, delete on public.analysis_runs to authenticated;
