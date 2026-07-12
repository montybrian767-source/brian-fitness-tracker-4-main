from __future__ import annotations

import pandas as pd

from services.supabase_service import get_workouts


def get_strength_workout_history(days: int = 90) -> pd.DataFrame:
    rows, err = get_workouts(days=days)
    if err:
        return pd.DataFrame()
    return pd.DataFrame(rows or [])
