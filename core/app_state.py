from __future__ import annotations

from typing import Any

import streamlit as st


def get(key: str, default: Any = None) -> Any:
    return st.session_state.get(key, default)


def set_value(key: str, value: Any) -> None:
    st.session_state[key] = value


def pop(key: str, default: Any = None) -> Any:
    return st.session_state.pop(key, default)
