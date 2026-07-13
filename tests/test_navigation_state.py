from pathlib import Path

from core.routing import VALID_ROUTES, default_home_route, normalize_route


def test_active_route_state_is_defined_and_used():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "def set_active_route(route: str) -> None:" in app_text
    assert "st.session_state['active_route'] = route_key" in app_text
    assert "set_active_route(page)" in app_text
    assert "active_route = canonical_route_key(st.session_state.get('active_route'))" in app_text


def test_normalize_route_none_uses_default():
    assert normalize_route(None) == default_home_route()


def test_normalize_route_empty_uses_default():
    assert normalize_route("") == default_home_route()


def test_normalize_route_app_alias():
    assert normalize_route("app") == "ai_personal_coach"


def test_normalize_route_home_alias():
    assert normalize_route("home") == "home"


def test_normalize_route_ai_personal_coach_alias():
    assert normalize_route("AI Personal Coach") == "ai_personal_coach"


def test_normalize_route_command_center_alias():
    assert normalize_route("command center") == "command_center"


def test_normalize_route_invalid_falls_back():
    assert normalize_route("invalid route") == default_home_route()


def test_default_home_route_is_valid():
    assert default_home_route() in VALID_ROUTES
