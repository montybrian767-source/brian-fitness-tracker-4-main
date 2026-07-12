from __future__ import annotations

from typing import Any, Dict

import pandas as pd


def build_nutrition_intelligence(nutrition_df: pd.DataFrame, supplement_df: pd.DataFrame, goal: Dict[str, Any]) -> Dict[str, Any]:
    today = pd.Timestamp.today().date()
    daily = nutrition_df.copy() if isinstance(nutrition_df, pd.DataFrame) else pd.DataFrame()
    if not daily.empty and 'date' in daily.columns:
        daily['date'] = pd.to_datetime(daily['date'], errors='coerce').dt.date
        daily = daily[daily['date'] == today]

    calories = float(pd.to_numeric(daily.get('calories', 0), errors='coerce').fillna(0).sum()) if not daily.empty else 0.0
    protein = float(pd.to_numeric(daily.get('protein_g', 0), errors='coerce').fillna(0).sum()) if not daily.empty else 0.0
    carbs = float(pd.to_numeric(daily.get('carbs_g', 0), errors='coerce').fillna(0).sum()) if not daily.empty else 0.0
    fat = float(pd.to_numeric(daily.get('fat_g', 0), errors='coerce').fillna(0).sum()) if not daily.empty else 0.0
    water = float(pd.to_numeric(daily.get('water_oz', 0), errors='coerce').fillna(0).sum()) if not daily.empty else 0.0

    calorie_target = int(goal.get('calorie_target', 2400)) if isinstance(goal, dict) else 2400
    protein_target = int(goal.get('protein_target', 180)) if isinstance(goal, dict) else 180

    missing = []
    if daily.empty:
        missing.append('daily nutrition log')

    return {
        'calorie_target': calorie_target,
        'protein_target': protein_target,
        'hydration_target': 100,
        'current_progress': {
            'calories': calories,
            'protein_g': protein,
            'carbs_g': carbs,
            'fat_g': fat,
            'water_oz': water,
        },
        'training_day_adjustment': 'Add 25-40g carbs pre/post workout when training.',
        'recovery_nutrition_suggestion': 'Prioritize hydration and protein in the first 2 hours post-workout.',
        'missing_data_status': missing,
    }
