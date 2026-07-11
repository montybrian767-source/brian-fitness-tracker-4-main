create table if not exists public.coaching_feedback (
    id bigint generated always as identity primary key,
    created_at timestamptz default now(),
    workout_session_id text not null,
    recommendation_date date not null,
    recommended_category text,
    recommended_focus text,
    readiness_score numeric,
    feedback_rating text not null,
    notes text
);

alter table public.coaching_feedback enable row level security;

drop policy if exists "Allow public read coaching feedback"
on public.coaching_feedback;

drop policy if exists "Allow public insert coaching feedback"
on public.coaching_feedback;

drop policy if exists "Allow public update coaching feedback"
on public.coaching_feedback;

create policy "Allow public read coaching feedback"
on public.coaching_feedback
for select
to anon
using (true);

create policy "Allow public insert coaching feedback"
on public.coaching_feedback
for insert
to anon
with check (true);

create policy "Allow public update coaching feedback"
on public.coaching_feedback
for update
to anon
using (true)
with check (true);

create unique index if not exists coaching_feedback_session_idx
on public.coaching_feedback(workout_session_id);

create index if not exists coaching_feedback_date_idx
on public.coaching_feedback(recommendation_date);
