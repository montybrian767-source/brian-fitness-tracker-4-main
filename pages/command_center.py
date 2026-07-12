from __future__ import annotations

from typing import Any, Dict

import streamlit as st


def _text(value: Any, default: str = '-') -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def render_command_center(daily_command: Dict[str, Any]) -> str:
    command = daily_command if isinstance(daily_command, dict) else {}
    weekly = command.get('weekly_goal_progress', {}) if isinstance(command.get('weekly_goal_progress'), dict) else {}
    cardio = command.get('cardio_recommendation', {}) if isinstance(command.get('cardio_recommendation'), dict) else {}

    st.markdown("""
    <style>
    .dc-shell {display:grid; gap:14px;}
    .dc-hero {background:linear-gradient(135deg,#07111f,#0a2440 58%,#16506b); border:1px solid rgba(96,165,250,.45); border-radius:22px; padding:18px;}
    .dc-kicker {font-size:.74rem; letter-spacing:.17em; color:#86efac; font-weight:900; text-transform:uppercase;}
    .dc-title {font-size:2rem; color:#ffffff; font-weight:900; line-height:1.1; margin-top:6px;}
    .dc-sub {color:#dbeafe; margin-top:8px;}
    .dc-mission {background:linear-gradient(145deg,#0b1b2e,#0a1220); border:1px solid rgba(34,197,94,.38); border-radius:22px; padding:16px;}
    .dc-grid {display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:10px;}
    .dc-chip {background:rgba(37,99,235,.20); border:1px solid rgba(96,165,250,.35); border-radius:12px; padding:9px 10px; color:#dbeafe;}
    .dc-section {background:#0a1423; border:1px solid rgba(96,165,250,.22); border-radius:18px; padding:14px;}
    @media (max-width: 850px) {
      .dc-grid {grid-template-columns:1fr;}
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="dc-shell">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="dc-hero">
            <div class="dc-kicker">Daily Command Center</div>
            <div class="dc-title">{_text(command.get('greeting'), 'Good Morning Brian')}</div>
            <div class="dc-sub">Readiness {_text(command.get('readiness_score'), 'N/A')}/100 • {_text(command.get('readiness_label'), 'Unknown')} • Confidence {_text(command.get('confidence_score'), 'N/A')}%</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="dc-mission">
            <div class="dc-kicker">Today's Mission</div>
            <div style="font-size:1.6rem;color:#fff;font-weight:900;">{_text(command.get('recommended_focus'), 'Upper Body Strength')}</div>
            <div class="dc-grid" style="margin-top:10px;">
                <div class="dc-chip">Readiness: {_text(command.get('readiness_score'), '78')}/100 - {_text(command.get('readiness_label'), 'Good')}</div>
                <div class="dc-chip">Intensity: {_text(command.get('intensity'), 'Moderate-Heavy')}</div>
                <div class="dc-chip">Duration: {_text(command.get('estimated_duration'), '55')} minutes</div>
                <div class="dc-chip">Cardio: {_text(cardio.get('duration_minutes'), '15')}-minute {_text(cardio.get('activity_type'), 'Zone 2')} finisher</div>
            </div>
            <div style="margin-top:10px;color:#cfe4ff;">Reason: {_text(command.get('main_reason'), 'Recommendation based on readiness and recent workload.')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    a1, a2, a3, a4, a5 = st.columns(5)
    action = ''
    if a1.button("Start Today's Workout", width='stretch'):
        action = 'start_workout'
    if a2.button('Preview Workout', width='stretch'):
        action = 'preview_workout'
    if a3.button('Adjust Plan', width='stretch'):
        action = 'adjust_plan'
    if a4.button('Recovery Instead', width='stretch'):
        action = 'recovery_instead'
    if a5.button('Log Activity', width='stretch'):
        action = 'log_activity'

    st.markdown('### Weekly Mission')
    w1, w2, w3 = st.columns(3)
    strength = weekly.get('strength', {}) if isinstance(weekly.get('strength'), dict) else {}
    cardio_week = weekly.get('cardio_minutes', {}) if isinstance(weekly.get('cardio_minutes'), dict) else {}
    w1.metric('Strength', _text(strength.get('label'), '0 of 4 completed'))
    w2.metric('Cardio', _text(cardio_week.get('label'), '0 of 150 minutes'))
    w3.metric('Body Weight Trend', _text(command.get('health_summary', {}).get('weight_trend'), 'No trend yet'))

    s1, s2, s3 = st.columns(3)
    health = command.get('health_summary', {}) if isinstance(command.get('health_summary'), dict) else {}
    nutrition = command.get('nutrition_summary', {}) if isinstance(command.get('nutrition_summary'), dict) else {}
    s1.metric('Apple Activity Status', 'Available' if not health.get('missing_data') else 'Partial')
    s2.metric('Nutrition Status', 'Tracked' if nutrition else 'Missing')
    s3.metric('Latest PR', _text(command.get('latest_pr'), 'No PR yet'))

    alerts = command.get('alerts', []) if isinstance(command.get('alerts'), list) else []
    for note in alerts:
        st.warning(str(note))

    st.markdown('</div>', unsafe_allow_html=True)
    return action
