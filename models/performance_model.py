from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PerformanceModel:
    weekly_performance_grade: int
    monthly_performance_grade: int
    progression_confidence: int
    recent_wins: List[Dict[str, Any]] = field(default_factory=list)
    plateau_alerts: List[Dict[str, Any]] = field(default_factory=list)
