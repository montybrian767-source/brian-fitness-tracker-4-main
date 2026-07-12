from __future__ import annotations

from datetime import date
from typing import Any, Dict, List


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(float(value))
    except Exception:
        return int(default)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _to_text(value: Any, default: str = '') -> str:
    if value is None:
        return default
    return str(value)


def _readiness_label(score: int) -> str:
    if score >= 85:
        return 'Excellent'
    if score >= 75:
        return 'Good'
    if score >= 65:
        return 'Moderate'
    return 'Recovery Focus'


def _build_weekly_goal_progress(strength_summary: Dict[str, Any], cardio_summary: Dict[str, Any], user_goals: Dict[str, Any]) -> Dict[str, Any]:
    strength_done = _to_int(strength_summary.get('days_trained_7', strength_summary.get('sessions_7', 0)), 0)
    strength_target = max(1, _to_int(user_goals.get('strength_workouts_per_week', 4), 4))
    cardio_done = _to_int(cardio_summary.get('weekly_minutes', 0), 0)
    cardio_target = max(1, _to_int(user_goals.get('cardio_minutes_per_week', 150), 150))
    return {
        'strength': {
            'current': strength_done,
            'target': strength_target,
            'label': f'{strength_done} of {strength_target} completed',
        },
        'cardio_minutes': {
            'current': cardio_done,
            'target': cardio_target,
            'label': f'{cardio_done} of {cardio_target} minutes',
        },
    }


def build_daily_command(
    target_date,
    readiness_result,
    coaching_plan,
    generated_workout,
    strength_summary,
    cardio_summary,
    apple_summary,
    body_summary,
    nutrition_summary,
    coaching_memory,
    user_goals,
    user_preferences,
):
    readiness_result = readiness_result if isinstance(readiness_result, dict) else {}
    coaching_plan = coaching_plan if isinstance(coaching_plan, dict) else {}
    generated_workout = generated_workout if isinstance(generated_workout, dict) else {}
    strength_summary = strength_summary if isinstance(strength_summary, dict) else {}
    cardio_summary = cardio_summary if isinstance(cardio_summary, dict) else {}
    apple_summary = apple_summary if isinstance(apple_summary, dict) else {}
    body_summary = body_summary if isinstance(body_summary, dict) else {}
    nutrition_summary = nutrition_summary if isinstance(nutrition_summary, dict) else {}
    coaching_memory = coaching_memory if isinstance(coaching_memory, dict) else {}
    user_goals = user_goals if isinstance(user_goals, dict) else {}
    user_preferences = user_preferences if isinstance(user_preferences, dict) else {}

    target = _to_text(target_date, date.today().isoformat())
    readiness_score = _to_int(
        coaching_plan.get('readiness_score', readiness_result.get('readiness_score', 70)),
        70,
    )
    readiness_label = _to_text(
        coaching_plan.get('recovery_status', readiness_result.get('recovery_status', _readiness_label(readiness_score))),
        _readiness_label(readiness_score),
    )

    recommended_category = _to_text(
        coaching_plan.get('recommended_category', generated_workout.get('workout_category', 'Strength')),
        'Strength',
    )
    recommended_focus = _to_text(
        coaching_plan.get('recommended_focus', generated_workout.get('workout_focus', generated_workout.get('focus', 'Full Body Strength'))),
        'Full Body Strength',
    )
    intensity = _to_text(
        coaching_plan.get('intensity_level', generated_workout.get('intensity', 'Moderate')),
        'Moderate',
    )
    estimated_duration = _to_int(
        coaching_plan.get('duration_minutes', generated_workout.get('expected_duration', generated_workout.get('estimated_duration_min', 55))),
        55,
    )
    volume_adjustment = _to_int(coaching_plan.get('volume_adjustment_percent', 0), 0)

    cardio_recommendation = coaching_plan.get('cardio_recommendation', {})
    if not isinstance(cardio_recommendation, dict) or not cardio_recommendation:
        cardio_recommendation = {
            'activity_type': 'Zone 2 Cardio',
            'duration_minutes': 15,
            'intensity': 'Easy-Moderate',
            'rpe_target': 5.0,
        }

    workout_preview = list(coaching_plan.get('recommended_exercises') or generated_workout.get('exercise_sequence') or generated_workout.get('recommended_exercises') or [])

    main_reason = _to_text(
        coaching_plan.get('main_reason', generated_workout.get('reasoning', generated_workout.get('coaching_note', 'Recommendation based on readiness and recent training load.'))),
        'Recommendation based on readiness and recent training load.',
    )

    positive_factors = [str(x) for x in (coaching_plan.get('positive_factors') or []) if str(x).strip()]
    limiting_factors = [str(x) for x in (coaching_plan.get('limiting_factors') or []) if str(x).strip()]

    if not positive_factors and _to_float(apple_summary.get('exercise_minutes', 0), 0.0) > 0:
        positive_factors.append('Recent activity data is available from Apple Health import.')
    if not limiting_factors and readiness_score < 75:
        limiting_factors.append('Readiness below optimal threshold, keep loading conservative.')

    health_summary = {
        'steps': apple_summary.get('steps'),
        'active_calories': apple_summary.get('active_energy_kcal'),
        'exercise_minutes': apple_summary.get('exercise_minutes'),
        'sleep_hours': apple_summary.get('sleep_hours'),
        'resting_heart_rate': apple_summary.get('resting_heart_rate'),
        'weight_lbs': body_summary.get('weight_lbs'),
        'weight_trend': body_summary.get('weight_trend'),
        'missing_data': list(apple_summary.get('missing_data') or []),
    }

    weekly_goal_progress = _build_weekly_goal_progress(strength_summary, cardio_summary, user_goals)
    confidence_score = _to_int(coaching_plan.get('confidence_score', generated_workout.get('confidence', 65)), 65)

    missing_data = []
    missing_data.extend([str(x) for x in (coaching_plan.get('missing_data') or []) if str(x).strip()])
    missing_data.extend([str(x) for x in (apple_summary.get('missing_data') or []) if str(x).strip()])
    data_quality = {
        'missing_data': sorted(set(missing_data)),
        'has_readiness': bool(readiness_result),
        'has_coaching_plan': bool(coaching_plan),
        'has_workout_preview': bool(workout_preview),
    }

    suggested_actions: List[str] = [
        'Start Today\'s Workout',
        'Preview Workout',
        'Adjust Plan',
        'Recovery Instead',
        'Log Activity',
    ]

    alerts = []
    if readiness_score < 65:
        alerts.append('Readiness is low today. Recovery-focused session is recommended.')
    if data_quality['missing_data']:
        alerts.append('Some data sources are missing; recommendations use conservative defaults.')

    return {
        'target_date': target,
        'greeting': 'Good Morning Brian',
        'readiness_score': readiness_score,
        'readiness_label': readiness_label,
        'recommended_category': recommended_category,
        'recommended_focus': recommended_focus,
        'intensity': intensity,
        'estimated_duration': estimated_duration,
        'volume_adjustment': volume_adjustment,
        'cardio_recommendation': cardio_recommendation,
        'workout_preview': workout_preview,
        'main_reason': main_reason,
        'positive_factors': positive_factors,
        'limiting_factors': limiting_factors,
        'health_summary': health_summary,
        'nutrition_summary': nutrition_summary,
        'weekly_goal_progress': weekly_goal_progress,
        'confidence_score': confidence_score,
        'data_quality': data_quality,
        'suggested_actions': suggested_actions,
        'alerts': alerts,
        'coaching_memory_notes': list(coaching_memory.get('notes', [])),
        'user_preferences': user_preferences,
    }
