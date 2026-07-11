create table if not exists public.cardio_sessions (
    id bigint generated always as identity primary key,
    created_at timestamptz default now(),
    workout_session_id text not null,
    activity_date date not null,
    start_time timestamptz,
    end_time timestamptz,
    activity_type text not null,
    category text default 'cardio',
    duration_minutes numeric not null,
    distance_value numeric,
    distance_unit text,
    calories_burned numeric,
    average_heart_rate numeric,
    maximum_heart_rate numeric,
    average_pace text,
    average_speed numeric,
    incline_percent numeric,
    resistance_level numeric,
    laps numeric,
    pool_length numeric,
    pool_length_unit text,
    steps numeric,
    rpe numeric,
    notes text,
    source text default 'Brian Fit',
    apple_workout_key text,
    verified boolean default false
);

alter table public.cardio_sessions enable row level security;

drop policy if exists "Allow public read cardio sessions"
on public.cardio_sessions;

drop policy if exists "Allow public insert cardio sessions"
on public.cardio_sessions;

drop policy if exists "Allow public update cardio sessions"
on public.cardio_sessions;

create policy "Allow public read cardio sessions"
on public.cardio_sessions
for select
to anon
using (true);

create policy "Allow public insert cardio sessions"
on public.cardio_sessions
for insert
to anon
with check (true);

create policy "Allow public update cardio sessions"
on public.cardio_sessions
for update
to anon
using (true)
with check (true);

create unique index if not exists cardio_session_unique_activity
on public.cardio_sessions (
    workout_session_id,
    activity_type,
    activity_date
);

create index if not exists cardio_sessions_date_idx
on public.cardio_sessions(activity_date);

create index if not exists cardio_sessions_type_idx
on public.cardio_sessions(activity_type);

create index if not exists cardio_sessions_session_idx
on public.cardio_sessions(workout_session_id);
