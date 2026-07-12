from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class TrainingRecommendationModel:
    workout_category: str
    workout_focus: str
    intensity: str
    expected_duration: int
    exercise_sequence: List[Dict[str, Any]] = field(default_factory=list)
    reasoning: str = ''
