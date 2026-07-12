from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd


def build_coaching_memory(feedback_df: pd.DataFrame, workout_log_df: pd.DataFrame, cardio_df: pd.DataFrame) -> Dict[str, Any]:
    notes: List[str] = []
    observations: List[Dict[str, Any]] = []

    if isinstance(feedback_df, pd.DataFrame) and not feedback_df.empty and 'feedback_rating' in feedback_df.columns:
        ratings = feedback_df['feedback_rating'].astype(str)
        too_hard = int((ratings == 'Too Hard').sum())
        about_right = int((ratings == 'About Right').sum())
        if too_hard > 0:
            notes.append('Recommendations are occasionally too aggressive; keep conservative loading guardrails.')
            observations.append({
                'memory_type': 'recommendation_accuracy',
                'memory_key': 'too_hard_frequency',
                'summary': f"Too Hard feedback observed {too_hard} time(s).",
                'confidence': min(0.95, 0.40 + (too_hard * 0.10)),
            })
        if about_right > 0:
            observations.append({
                'memory_type': 'recommendation_accuracy',
                'memory_key': 'about_right_frequency',
                'summary': f"About Right feedback observed {about_right} time(s).",
                'confidence': min(0.95, 0.45 + (about_right * 0.08)),
            })

    if isinstance(cardio_df, pd.DataFrame) and not cardio_df.empty and 'activity_type' in cardio_df.columns:
        cardio_types = cardio_df['activity_type'].astype(str).value_counts().head(3).index.tolist()
        if cardio_types:
            notes.append('Frequent cardio activities influence next-day strength readiness.')
            observations.append({
                'memory_type': 'schedule_pattern',
                'memory_key': 'top_cardio_types',
                'summary': f"Frequent cardio types: {', '.join(cardio_types)}.",
                'confidence': 0.65,
            })

    return {
        'notes': notes,
        'observations': observations,
    }
