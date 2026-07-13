from __future__ import annotations

from typing import Any, Dict

import streamlit as st


def _text(value: Any, default: str = 'Unknown') -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _ok_badge(value: Any) -> str:
    text = _text(value, 'Unknown')
    norm = text.lower()
    if any(token in norm for token in ['connected', 'available', 'ready', 'healthy', 'yes', 'ok']):
        return 'status-ok'
    if any(token in norm for token in ['warning', 'degraded', 'missing', 'fallback']):
        return 'status-warn'
    if any(token in norm for token in ['unavailable', 'error', 'failed', 'no']):
        return 'status-error'
    return ''


def render_system_center(system_status: Dict[str, Any]) -> None:
    status = system_status if isinstance(system_status, dict) else {}
    latency_raw = status.get('supabase_latency_ms', None)
    try:
        latency_text = f"{float(latency_raw):.0f} ms" if latency_raw is not None else 'N/A'
    except Exception:
        latency_text = 'N/A'

    supabase_connected = _text(status.get('supabase_connected', status.get('supabase', 'Unknown')))
    workouts_ready = _text(status.get('workouts_table_ready', 'Unknown'))
    cardio_ready = _text(status.get('cardio_table_ready', 'Unknown'))
    apple_ready = _text(status.get('apple_tables_ready', 'Unknown'))
    supabase_error = _text(status.get('supabase_error', ''), '')

    st.markdown(
        """
        <div class="side-card" style="margin-bottom:10px;">
          <div class="side-title">System Center</div>
          <div class="small">Production diagnostics for daily release quality.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('### Release Health')
    r1, r2, r3, r4 = st.columns(4)
    r1.metric('Version', _text(status.get('version')))
    r2.metric('Build', _text(status.get('build')))
    r3.metric('Release Health', _text(status.get('release_health', 'Ready')))
    r4.metric('Active Route', _text(status.get('active_route', 'Unknown')))

    st.markdown('### Core Systems')
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Supabase', _text(status.get('supabase', 'Unknown')))
    c2.metric('Apple', _text(status.get('apple', 'Unknown')))
    c3.metric('Recovery', _text(status.get('recovery_engine', 'Unknown')))
    c4.metric('AI Coach', _text(status.get('ai_coach', 'Unknown')))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric('Performance', _text(status.get('performance', 'Unknown')))
    d2.metric('Cache', _text(status.get('cache', 'Unknown')))
    d3.metric('Last Workout Save', _text(status.get('last_workout_save', '-')))
    d4.metric('Last Cardio Save', _text(status.get('last_cardio_save', '-')))

    st.caption(f"Last Apple import: {_text(status.get('last_apple_import', '-'))}")

    st.markdown('### Supabase Health')
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric('Supabase', supabase_connected)
    s2.metric('Workouts Table', workouts_ready)
    s3.metric('Cardio Table', cardio_ready)
    s4.metric('Apple Tables', apple_ready)
    s5.metric('Latency', latency_text)
    if supabase_error:
        st.caption(f"Error: {supabase_error}")

    st.markdown('### System Status')
    summary_rows = [
        ('Supabase', _text(status.get('supabase', 'Unknown'))),
        ('Apple Data', _text(status.get('apple', 'Unknown'))),
        ('Recovery Engine', _text(status.get('recovery_engine', 'Unknown'))),
        ('AI Coach', _text(status.get('ai_coach', 'Unknown'))),
        ('Performance', _text(status.get('performance', 'Unknown'))),
        ('Cache', _text(status.get('cache', 'Unknown'))),
        ('Release Health', _text(status.get('release_health', 'Ready'))),
    ]
    for label, value in summary_rows:
        badge_class = _ok_badge(value)
        st.markdown(
            f"<div class='history-session-card'><b>{label}</b><br><span class='{badge_class}'>{value}</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown('### Feature Flags')
    flags = status.get('flags', {}) if isinstance(status.get('flags'), dict) else {}
    if not flags:
        st.caption('No feature flags are currently configured.')
    else:
        for name, enabled in flags.items():
            st.write(f"- {name}: {'ON' if bool(enabled) else 'OFF'}")

    with st.expander('Raw diagnostics payload', expanded=False):
        st.json(status)
