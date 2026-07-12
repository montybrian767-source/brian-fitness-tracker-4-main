from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from engines.recovery_readiness_engine import calculate_daily_readiness


def build_recovery_intelligence(
    target_date,
    apple_daily_data: pd.DataFrame,
    apple_workouts_data: pd.DataFrame,
    strength_workouts: pd.DataFrame,
    recent_cardio_data: pd.DataFrame,
    body_stats: pd.DataFrame,
) -> Dict[str, Any]:
    result = calculate_daily_readiness(
        target_date=target_date,
        apple_daily_data=apple_daily_data,
        apple_workouts_data=apple_workouts_data,
        strength_workouts=strength_workouts,
        recent_cardio_data=recent_cardio_data,
        body_stats=body_stats,
    )

    recommendation = result.get('recommendation', {}) if isinstance(result, dict) else {}
    score = int(result.get('readiness_score', 70) or 70)
    return {
        'overall_readiness': score,
        'recovery_status': result.get('recovery_status', 'Moderate'),
        'systemic_fatigue': result.get('systemic_fatigue_flag', 'unknown'),
        'upper_body_readiness': result.get('upper_body_readiness', score),
        'lower_body_readiness': result.get('lower_body_readiness', score),
        'muscle_group_readiness': result.get('muscle_group_readiness', {}),
        'limiting_factors': result.get('limiting_factors', []),
        'positive_factors': result.get('positive_factors', []),
        'recommended_intensity': recommendation.get('primary_recommendation', 'Moderate Session'),
        'recommended_volume_adjustment': recommendation.get('suggested_volume_adjustment', 'No change'),
        'recovery_actions': recommendation.get('recovery_actions', []),
        'confidence': result.get('confidence_score', 60),
        'missing_data': result.get('missing_data', []),
        'raw': result,
    }
