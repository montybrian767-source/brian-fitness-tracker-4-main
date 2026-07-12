from __future__ import annotations

from typing import Any, Dict

import pandas as pd


def _safe_latest(df: pd.DataFrame, date_col: str):
    if df.empty or date_col not in df.columns:
        return {}
    tmp = df.copy()
    tmp[date_col] = pd.to_datetime(tmp[date_col], errors='coerce', utc=True)
    tmp = tmp.dropna(subset=[date_col]).sort_values(date_col)
    if tmp.empty:
        return {}
    return tmp.iloc[-1].to_dict()


def build_health_intelligence(apple_daily_df: pd.DataFrame, body_df: pd.DataFrame) -> Dict[str, Any]:
    latest_activity = _safe_latest(apple_daily_df, 'activity_date')
    latest_body = _safe_latest(body_df, 'date')

    missing = []
    for key in ['steps', 'active_energy_kcal', 'exercise_minutes', 'sleep_hours', 'resting_heart_rate', 'heart_rate_variability_ms']:
        if latest_activity.get(key) is None or (isinstance(latest_activity.get(key), float) and pd.isna(latest_activity.get(key))):
            missing.append(key)

    return {
        'daily_health_summary': {
            'steps': latest_activity.get('steps'),
            'active_calories': latest_activity.get('active_energy_kcal'),
            'exercise_minutes': latest_activity.get('exercise_minutes'),
            'stand_hours': latest_activity.get('stand_hours'),
            'sleep_hours': latest_activity.get('sleep_hours'),
        },
        'weekly_health_summary': {
            'activity_consistency': 'Available' if not apple_daily_df.empty else 'No weekly data',
        },
        'activity_consistency': 'Good' if len(apple_daily_df.index) >= 5 else 'Limited data',
        'recovery_signals': {
            'resting_heart_rate': latest_activity.get('resting_heart_rate'),
            'hrv_ms': latest_activity.get('heart_rate_variability_ms'),
        },
        'cardio_fitness_trend': latest_activity.get('vo2_max') if 'vo2_max' in latest_activity else None,
        'weight_trend': latest_body.get('body_weight_lbs'),
        'missing_data_status': missing,
    }
