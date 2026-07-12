from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class DailyCommandModel:
    target_date: str
    greeting: str
    readiness_score: int
    readiness_label: str
    recommended_category: str
    recommended_focus: str
    intensity: str
    estimated_duration: int
    main_reason: str
    cardio_recommendation: Dict[str, Any] = field(default_factory=dict)
    weekly_goal_progress: Dict[str, Any] = field(default_factory=dict)
    suggested_actions: List[str] = field(default_factory=list)
