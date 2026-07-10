create table if not exists public.apple_activity_daily (
    id bigint generated always as identity primary key,
    activity_date date not null unique,
    steps numeric default 0,
    active_energy_kcal numeric default 0,
    active_energy_goal_kcal numeric,
    basal_energy_kcal numeric default 0,
    exercise_minutes numeric default 0,
    exercise_goal_minutes numeric,
    stand_hours numeric default 0,
    stand_goal_hours numeric,
    walking_running_distance_miles numeric default 0,
    flights_climbed numeric default 0,
    resting_heart_rate numeric,
    walking_heart_rate_average numeric,
    heart_rate_variability_ms numeric,
    average_heart_rate numeric,
    maximum_heart_rate numeric,
    sleep_hours numeric,
    source text default 'Apple Health',
    imported_at timestamptz default now()
);

create table if not exists public.apple_workouts (
    id bigint generated always as identity primary key,
    apple_workout_key text not null unique,
    workout_type text,
    start_time timestamptz,
    end_time timestamptz,
    duration_minutes numeric,
    total_energy_kcal numeric,
    total_distance_miles numeric,
    average_heart_rate numeric,
    maximum_heart_rate numeric,
    source_name text,
    source_version text,
    device text,
    metadata jsonb,
    imported_at timestamptz default now()
);

alter table public.apple_activity_daily enable row level security;
alter table public.apple_workouts enable row level security;

drop policy if exists "Allow public read apple activity" on public.apple_activity_daily;
drop policy if exists "Allow public insert apple activity" on public.apple_activity_daily;
drop policy if exists "Allow public update apple activity" on public.apple_activity_daily;

create policy "Allow public read apple activity"
on public.apple_activity_daily
for select
to anon
using (true);

create policy "Allow public insert apple activity"
on public.apple_activity_daily
for insert
to anon
with check (true);

create policy "Allow public update apple activity"
on public.apple_activity_daily
for update
to anon
using (true)
with check (true);

drop policy if exists "Allow public read apple workouts" on public.apple_workouts;
drop policy if exists "Allow public insert apple workouts" on public.apple_workouts;

create policy "Allow public read apple workouts"
on public.apple_workouts
for select
to anon
using (true);

create policy "Allow public insert apple workouts"
on public.apple_workouts
for insert
to anon
with check (true);

create index if not exists apple_activity_daily_date_idx
on public.apple_activity_daily(activity_date);

create index if not exists apple_workouts_start_time_idx
on public.apple_workouts(start_time);

create index if not exists apple_workouts_type_idx
on public.apple_workouts(workout_type);