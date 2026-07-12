from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class CoachingMemoryModel:
    notes: List[str] = field(default_factory=list)
    observations: List[Dict[str, Any]] = field(default_factory=list)
