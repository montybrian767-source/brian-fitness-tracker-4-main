# Brian Fitness Tracker X — Sprint X.6 Elite Workout Experience

## What changed
- Rebuilt Today's Workout into an elite one-exercise command center.
- Larger exercise image area.
- Previous/best weight cards.
- Large COMPLETE SET button.
- Rest timer panel.
- Workout progress bar and finish workout summary.
- Keeps all existing data files, images, nutrition, supplements, progress, and AI Coach.

## What to test
1. Open Today's Workout.
2. Pick today's day.
3. Confirm the large exercise image appears.
4. Complete one set.
5. Confirm the app moves to the next exercise and workout_log.csv updates.
6. Click Finish Workout.

## Cloud Workout Sync (Sprint 10)
- Local backup remains active in `data/workout_log.csv`.
- If Supabase is configured, each completed set is also written to cloud table `workout_log`.
- If Supabase is not configured, the app still works and saves locally only.

### Streamlit secrets (required for cloud)
Add these in Streamlit Cloud app secrets (or local `.streamlit/secrets.toml`):

```toml
SUPABASE_URL = "https://your-project-id.supabase.co"
SUPABASE_KEY = "your-supabase-anon-or-service-key"
```

Do not hardcode credentials in source files and do not commit secrets.
