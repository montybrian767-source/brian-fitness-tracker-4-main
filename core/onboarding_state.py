from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import Any


def apply_skip_onboarding_state(state: MutableMapping[str, Any], destination: str = 'home') -> None:
    state['onboarding_complete'] = True
    state['onboarding_completed'] = True
    state['onboarding_skipped'] = True
    state['onboarding_step'] = 0
    state['active_route'] = destination
    state['current_page'] = destination
    state['mobile_route'] = destination
    state['mobile_nav_override'] = 'Home'


def apply_completed_onboarding_state(state: MutableMapping[str, Any], destination: str = 'home') -> None:
    state['onboarding_complete'] = True
    state['onboarding_completed'] = True
    state['onboarding_skipped'] = False
    state['onboarding_step'] = 0
    state['active_route'] = destination
    state['current_page'] = destination
    state['mobile_route'] = destination
    state['mobile_nav_override'] = 'Home'


def should_show_onboarding(session_state: MutableMapping[str, Any], persisted_complete: bool, preferences_complete: bool) -> bool:
    if bool(session_state.get('onboarding_completed')):
        return False
    if bool(session_state.get('onboarding_skipped')):
        return False
    if persisted_complete:
        return False
    if preferences_complete:
        return False
    return True


def safe_onboarding_persist(save_fn: Callable[[], None]) -> str:
    try:
        save_fn()
        return ''
    except Exception as exc:
        return str(exc)
