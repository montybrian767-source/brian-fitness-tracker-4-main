from __future__ import annotations

import pandas as pd

from services.workout_save_service import get_cardio_sessions


def get_cardio_history(days: int = 90) -> pd.DataFrame:
    rows, _ = get_cardio_sessions(days=days)
    return pd.DataFrame(rows or [])
