from pathlib import Path


def test_active_route_state_is_defined_and_used():
    app_text = Path("app.py").read_text(encoding="utf-8")

    assert "def set_active_route(route: str) -> None:" in app_text
    assert "st.session_state['active_route'] = target" in app_text
    assert "set_active_route(page)" in app_text
    assert "current = str(st.session_state.get('active_route'" in app_text
