from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from engines.workout_recommendation_engine import generate_next_workout


def build_training_intelligence(
    readiness_result: Dict[str, Any],
    recent_strength_performance: pd.DataFrame,
    recent_cardio_load: pd.DataFrame,
    apple_workouts: pd.DataFrame,
    goal: Dict[str, Any],
    preferred_split: str,
    available_equipment: str,
    exercise_history: pd.DataFrame,
    exercise_rotation_status: Dict[str, Any],
    planned_sport_sessions: pd.DataFrame,
    user_preferences: Dict[str, Any],
    workouts_df: pd.DataFrame,
) -> Dict[str, Any]:
    plan = generate_next_workout(exercise_history, workouts_df)

    return {
        'workout_category': plan.get('category', 'Strength' if user_preferences else 'Mixed'),
        'workout_focus': plan.get('focus', preferred_split or 'Balanced Split'),
        'warm_up': ['5 minutes brisk walk', 'dynamic mobility sequence'],
        'exercise_sequence': plan.get('recommended_exercises', []),
        'target_sets': [item.get('suggested_sets', 3) for item in plan.get('recommended_exercises', [])],
        'target_reps': [item.get('suggested_rep_range', '8-12') for item in plan.get('recommended_exercises', [])],
        'target_weight': [item.get('suggested_starting_weight', 0) for item in plan.get('recommended_exercises', [])],
        'target_rpe': 7.0,
        'rest_time': [item.get('rest_seconds', 90) for item in plan.get('recommended_exercises', [])],
        'cardio_block': {
            'type': 'Zone 2',
            'duration_minutes': 15,
            'intensity': 'Easy-Moderate',
        },
        'substitutions': {},
        'expected_duration': plan.get('estimated_duration_min', 55),
        'confidence': 70,
        'reasoning': plan.get('coaching_note', 'Generated from existing Smart Workout Builder logic.'),
    }
