from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from engines.plateau_detection_engine import detect_plateaus
from engines.progressive_overload_engine import analyze_progressive_overload


def _reason(action: str, item: Dict[str, Any]) -> str:
    if action == 'progress':
        return f"Progression supported by trend {item.get('performance_trend', 'stable')} and manageable RPE."
    if action == 'hold':
        return f"Hold load due to trend {item.get('performance_trend', 'stable')} and current fatigue profile."
    return f"Reduce temporarily due to elevated strain (RPE {item.get('last_rpe', 'N/A')})."


def build_performance_intelligence(log_df: pd.DataFrame, workouts_df: pd.DataFrame, cardio_df: pd.DataFrame) -> Dict[str, Any]:
    progression = analyze_progressive_overload(log_df, workouts_df)
    plateau = detect_plateaus(log_df)

    ready_to_progress: List[Dict[str, Any]] = []
    hold_list: List[Dict[str, Any]] = []
    reduce_list: List[Dict[str, Any]] = []

    for item in progression.get('recommendations', [])[:20]:
        action = str(item.get('suggested_action', 'Hold Weight')).lower()
        payload = {
            'exercise': item.get('exercise', ''),
            'action': item.get('suggested_action', 'Hold Weight'),
            'why': _reason('progress' if 'increase' in action else ('reduce' if 'reduce' in action or 'recovery' in action else 'hold'), item),
        }
        if 'increase' in action:
            ready_to_progress.append(payload)
        elif 'reduce' in action or 'recovery' in action:
            reduce_list.append(payload)
        else:
            hold_list.append(payload)

    weekly_grade = min(100, 60 + len(ready_to_progress) * 4 - len(reduce_list) * 3)
    monthly_grade = min(100, 58 + len(progression.get('recommendations', [])) * 2)

    return {
        'recent_wins': progression.get('wins', []),
        'exercises_ready_to_progress': ready_to_progress,
        'exercises_to_hold': hold_list,
        'exercises_to_reduce': reduce_list,
        'plateau_alerts': plateau.get('plateaus', []),
        'rotation_candidates': plateau.get('rotation_candidates', []),
        'progression_confidence': progression.get('confidence', 65),
        'weekly_performance_grade': weekly_grade,
        'monthly_performance_grade': monthly_grade,
    }
