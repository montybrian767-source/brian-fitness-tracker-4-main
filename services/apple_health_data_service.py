from __future__ import annotations

from typing import Tuple

import pandas as pd

from services.apple_health_import_service import get_apple_activity_daily, get_apple_workouts_dataframe


def get_apple_health_frames() -> Tuple[pd.DataFrame, pd.DataFrame]:
    daily_df, _ = get_apple_activity_daily()
    workouts_df, _, _ = get_apple_workouts_dataframe(limit=2000, offset=0)
    return daily_df if isinstance(daily_df, pd.DataFrame) else pd.DataFrame(), workouts_df if isinstance(workouts_df, pd.DataFrame) else pd.DataFrame()
