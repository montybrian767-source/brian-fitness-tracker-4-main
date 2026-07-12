from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, DefaultDict, Dict, List


EventHandler = Callable[[str, Dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: DefaultDict[str, List[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        if handler not in self._handlers[event_name]:
            self._handlers[event_name].append(handler)

    def publish(self, event_name: str, payload: Dict[str, Any] | None = None) -> None:
        data = payload if isinstance(payload, dict) else {}
        for handler in list(self._handlers.get(event_name, [])):
            handler(event_name, data)


EVENT_BUS = EventBus()


SUPPORTED_EVENTS = {
    'strength_workout_saved',
    'cardio_session_saved',
    'mixed_workout_saved',
    'apple_import_completed',
    'body_stats_updated',
    'nutrition_updated',
    'goals_updated',
    'preferences_updated',
    'coaching_feedback_saved',
    'workout_plan_changed',
}
