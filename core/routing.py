from __future__ import annotations

from core.feature_flags import is_enabled


def default_home_route() -> str:
    return 'Command Center' if is_enabled('FITNESS_OS_COMMAND_CENTER', default=True) else 'Dashboard'
