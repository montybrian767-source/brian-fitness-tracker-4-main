from __future__ import annotations

from typing import Any, Callable, Dict, Iterable

from core.event_bus import EVENT_BUS


def register_cache_invalidation(invalidation_map: Dict[str, Iterable[Callable[[], None]]]) -> None:
    for event_name, handlers in (invalidation_map or {}).items():
        for callback in list(handlers or []):
            EVENT_BUS.subscribe(
                event_name,
                lambda _event, _payload, fn=callback: fn(),
            )


def publish_event(event_name: str, payload: Dict[str, Any] | None = None) -> None:
    EVENT_BUS.publish(event_name, payload if isinstance(payload, dict) else {})
