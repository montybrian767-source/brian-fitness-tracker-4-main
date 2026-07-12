from __future__ import annotations

import os
from typing import Any

import streamlit as st


DEFAULT_FLAGS = {
    'FITNESS_OS_COMMAND_CENTER': True,
    'FITNESS_OS_TRAINING_INTELLIGENCE': False,
    'FITNESS_OS_COACHING_MEMORY': False,
    'FITNESS_OS_NUTRITION_FOUNDATION': False,
    'FITNESS_OS_HEALTH_INTELLIGENCE': False,
}


def _parse_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {'1', 'true', 'yes', 'on', 'enabled'}:
        return True
    if text in {'0', 'false', 'no', 'off', 'disabled'}:
        return False
    return None


def _secret_flags() -> dict:
    try:
        secret_value = st.secrets.get('FEATURE_FLAGS', {})
    except Exception:
        return {}
    return secret_value if isinstance(secret_value, dict) else {}


def is_enabled(name: str, default: bool = False) -> bool:
    session_override = _parse_bool(st.session_state.get(f'flag_{name}'))
    if session_override is not None:
        return session_override

    env_value = _parse_bool(os.getenv(name))
    if env_value is not None:
        return env_value

    secret_value = _parse_bool(_secret_flags().get(name))
    if secret_value is not None:
        return secret_value

    if name in DEFAULT_FLAGS:
        return bool(DEFAULT_FLAGS[name])
    return bool(default)


def all_flags() -> dict:
    return {flag: is_enabled(flag, default=default) for flag, default in DEFAULT_FLAGS.items()}
