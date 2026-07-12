from __future__ import annotations

from typing import Any, Dict

import streamlit as st


def render_system_center(system_status: Dict[str, Any]) -> None:
    status = system_status if isinstance(system_status, dict) else {}
    st.title('System Center')
    st.caption('Fitness Operating System diagnostics and feature availability.')

    c1, c2, c3 = st.columns(3)
    c1.metric('Supabase', status.get('supabase', 'Unknown'))
    c2.metric('Recovery Engine', status.get('recovery_engine', 'Unknown'))
    c3.metric('AI Coach', status.get('ai_coach', 'Unknown'))

    d1, d2, d3 = st.columns(3)
    d1.metric('Last Workout Save', status.get('last_workout_save', '-'))
    d2.metric('Last Cardio Save', status.get('last_cardio_save', '-'))
    d3.metric('Last Apple Import', status.get('last_apple_import', '-'))

    st.markdown('### Feature Flags')
    flags = status.get('flags', {}) if isinstance(status.get('flags'), dict) else {}
    for name, enabled in flags.items():
        st.write(f"- {name}: {'ON' if bool(enabled) else 'OFF'}")

    st.markdown('### Build')
    st.write(status.get('build', 'Unknown build'))
