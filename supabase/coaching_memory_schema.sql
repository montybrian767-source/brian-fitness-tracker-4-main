create table if not exists public.coaching_memory (
    id bigint generated always as identity primary key,
    created_at timestamptz default now(),
    memory_type text not null,
    memory_key text not null,
    summary text not null,
    confidence numeric default 0,
    evidence_count integer default 1,
    first_observed_at timestamptz,
    last_observed_at timestamptz,
    active boolean default true,
    metadata jsonb default '{}'::jsonb
);

create unique index if not exists coaching_memory_unique_key
on public.coaching_memory(memory_type, memory_key);

alter table public.coaching_memory enable row level security;

create policy if not exists coaching_memory_select_policy
on public.coaching_memory
for select
using (auth.role() = 'authenticated');

create policy if not exists coaching_memory_insert_policy
on public.coaching_memory
for insert
with check (auth.role() = 'authenticated');

create policy if not exists coaching_memory_update_policy
on public.coaching_memory
for update
using (auth.role() = 'authenticated')
with check (auth.role() = 'authenticated');
