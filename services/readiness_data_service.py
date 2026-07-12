from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from engines.recovery_readiness_engine import calculate_daily_readiness


def get_readiness(target_date, apple_daily: pd.DataFrame, apple_workouts: pd.DataFrame, strength_df: pd.DataFrame, cardio_df: pd.DataFrame, body_df: pd.DataFrame) -> Dict[str, Any]:
    return calculate_daily_readiness(
        target_date=target_date,
        apple_daily_data=apple_daily,
        apple_workouts_data=apple_workouts,
        strength_workouts=strength_df,
        recent_cardio_data=cardio_df,
        body_stats=body_df,
    )
