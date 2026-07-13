from core.onboarding_state import (
    apply_completed_onboarding_state,
    apply_skip_onboarding_state,
    safe_onboarding_persist,
    should_show_onboarding,
)
from core.routing import normalize_route, page_from_route, route_from_page


def test_desktop_skip_sets_required_state_fields():
    state = {}
    apply_skip_onboarding_state(state)

    assert state['onboarding_complete'] is True
    assert state['onboarding_completed'] is True
    assert state['onboarding_skipped'] is True
    assert state['onboarding_step'] == 0
    assert state['active_route'] == 'home'
    assert state['current_page'] == 'home'
    assert state['mobile_route'] == 'home'


def test_mobile_skip_preserves_valid_canonical_route_state():
    state = {'mobile_route': '', 'active_route': 'invalid'}
    apply_skip_onboarding_state(state)

    assert state['active_route'] == 'home'
    assert state['mobile_route'] == 'home'
    assert state['mobile_nav_override'] == 'Home'


def test_completed_onboarding_sets_destination_state():
    state = {}
    apply_completed_onboarding_state(state, destination='command_center')

    assert state['onboarding_completed'] is True
    assert state['onboarding_skipped'] is False
    assert state['active_route'] == 'command_center'


def test_empty_active_route_normalizes_to_home():
    assert normalize_route('') == 'home'
    assert normalize_route(None) == 'home'


def test_invalid_active_route_normalizes_to_home():
    assert normalize_route('not_a_real_route') == 'home'


def test_missing_onboarding_preferences_keeps_onboarding_visible():
    state = {}
    assert should_show_onboarding(state, persisted_complete=False, preferences_complete=False) is True


def test_persistence_save_failure_returns_error_without_blocking_state_logic():
    err = safe_onboarding_persist(lambda: (_ for _ in ()).throw(RuntimeError('disk full')))
    assert 'disk full' in err


def test_rerun_after_skip_does_not_reopen_onboarding():
    state = {'onboarding_skipped': True}
    assert should_show_onboarding(state, persisted_complete=False, preferences_complete=False) is False


def test_route_page_mappings_for_mobile_desktop_consistency():
    assert route_from_page('AI Personal Trainer') == 'ai_personal_coach'
    assert page_from_route('ai_personal_coach') == 'AI Personal Trainer'
    assert page_from_route('invalid_route') == 'Home'
