from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class RecoveryModel:
    overall_readiness: int
    recovery_status: str
    recommended_intensity: str
    limiting_factors: List[str] = field(default_factory=list)
    positive_factors: List[str] = field(default_factory=list)
    missing_data: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)
