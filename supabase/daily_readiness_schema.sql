create table if not exists public.daily_readiness (
    id bigint generated always as identity primary key,
    readiness_date date not null unique,
    readiness_score numeric,
    recovery_status text,
    confidence_score numeric,
    sleep_score numeric,
    hrv_score numeric,
    resting_hr_score numeric,
    activity_load_score numeric,
    strength_load_score numeric,
    recovery_balance_score numeric,
    recommendation jsonb,
    limiting_factors jsonb,
    positive_factors jsonb,
    data_quality jsonb,
    calculated_at timestamptz default now()
);

alter table public.daily_readiness enable row level security;

drop policy if exists "Allow public read daily readiness"
on public.daily_readiness;

drop policy if exists "Allow public insert daily readiness"
on public.daily_readiness;

drop policy if exists "Allow public update daily readiness"
on public.daily_readiness;

create policy "Allow public read daily readiness"
on public.daily_readiness
for select
to anon
using (true);

create policy "Allow public insert daily readiness"
on public.daily_readiness
for insert
to anon
with check (true);

create policy "Allow public update daily readiness"
on public.daily_readiness
for update
to anon
using (true)
with check (true);

create index if not exists daily_readiness_date_idx
on public.daily_readiness(readiness_date);
