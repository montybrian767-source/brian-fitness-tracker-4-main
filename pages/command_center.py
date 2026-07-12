from __future__ import annotations

from typing import Any, Dict

import streamlit as st
import pandas as pd


def _text(value: Any, default: str = '-') -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _metric(value: Any, suffix: str = '') -> str:
    if value is None:
        return 'Not available'
    if isinstance(value, float) and pd.isna(value):
        return 'Not available'
    text = str(value).strip()
    if not text or text.lower() == 'nan':
        return 'Not available'
    return f'{text}{suffix}'


def _ratio_label(current: Any, target: Any, unit: str = '') -> str:
    cur = _metric(current)
    tar = _metric(target)
    if cur == 'Not available' or tar == 'Not available':
        return 'Not available'
    suffix = f' {unit}'.rstrip()
    return f'{cur} of {tar}{suffix}'


def render_command_center(daily_command: Dict[str, Any]) -> str:
    command = daily_command if isinstance(daily_command, dict) else {}
    weekly = command.get('weekly_goal_progress', {}) if isinstance(command.get('weekly_goal_progress'), dict) else {}
    weekly_ext = command.get('weekly_mission_extended', {}) if isinstance(command.get('weekly_mission_extended'), dict) else {}
    snapshot = command.get('daily_snapshot', {}) if isinstance(command.get('daily_snapshot'), dict) else {}
    cardio = command.get('cardio_recommendation', {}) if isinstance(command.get('cardio_recommendation'), dict) else {}
    health = command.get('health_summary', {}) if isinstance(command.get('health_summary'), dict) else {}

    st.markdown("""
    <style>
        .dc-shell {display:grid; gap:16px;}
        .dc-hero {background:linear-gradient(130deg,#07111f,#0b2443 55%,#1f6d72); border:1px solid rgba(96,165,250,.45); border-radius:24px; padding:18px; box-shadow:0 18px 50px rgba(0,0,0,.36);}
        .dc-kicker {font-size:.73rem; letter-spacing:.2em; color:#86efac; font-weight:900; text-transform:uppercase;}
        .dc-title {font-size:2.05rem; color:#ffffff; font-weight:900; line-height:1.05; margin-top:7px;}
        .dc-sub {color:#dbeafe; margin-top:8px; line-height:1.4;}
        .dc-mission {background:linear-gradient(150deg,#0d1c31,#0a1322); border:1px solid rgba(34,197,94,.38); border-radius:22px; padding:16px;}
        .dc-mission-title {font-size:1.8rem;color:#fff;font-weight:900;margin-top:8px;}
        .dc-grid {display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:10px;}
        .dc-chip {background:rgba(37,99,235,.18); border:1px solid rgba(96,165,250,.30); border-radius:12px; padding:9px 10px; color:#dbeafe; min-height:58px;}
        .dc-chip-label {font-size:.74rem;color:#9cc7ff;font-weight:800;letter-spacing:.06em;text-transform:uppercase;}
        .dc-chip-value {font-size:.96rem;color:#fff;font-weight:800;margin-top:4px;}
        .dc-section {background:#0a1423; border:1px solid rgba(96,165,250,.22); border-radius:18px; padding:14px;}
        .dc-snapshot {display:grid; grid-template-columns:repeat(5, minmax(0,1fr)); gap:10px;}
        .dc-s-card {background:linear-gradient(180deg,#0b1a2c,#09111f); border:1px solid rgba(96,165,250,.22); border-radius:14px; padding:10px; min-height:86px;}
        .dc-s-label {font-size:.72rem; letter-spacing:.08em; text-transform:uppercase; color:#9cc7ff; font-weight:800;}
        .dc-s-value {font-size:.98rem; color:#fff; font-weight:800; margin-top:4px;}
        .dc-w-row {display:grid; grid-template-columns:140px 1fr 110px; gap:12px; align-items:center; margin:8px 0;}
        .dc-w-label {font-weight:800;color:#fff;}
        .dc-w-bar {height:10px;border-radius:999px;background:#13273f;border:1px solid #22405f;overflow:hidden;}
        .dc-w-fill {height:100%;border-radius:999px;background:linear-gradient(90deg,#22c55e,#38bdf8);}
        .dc-w-value {color:#dbeafe;font-weight:800;text-align:right;}
    @media (max-width: 850px) {
      .dc-grid {grid-template-columns:1fr;}
            .dc-snapshot {grid-template-columns:repeat(2, minmax(0,1fr));}
            .dc-title {font-size:1.7rem;}
            .dc-mission-title {font-size:1.45rem;}
            .dc-w-row {grid-template-columns:110px 1fr 90px;}
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="dc-shell">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="dc-hero">
            <div class="dc-kicker">Brian Fit X 10.2</div>
            <div class="dc-title">TODAY'S MISSION</div>
            <div class="dc-sub">Premium training guidance with readiness-aware recommendations, clean mobile controls, and focused actions.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    readiness_text = f"{_metric(command.get('readiness_score'))}/100 - {_text(command.get('readiness_label'), 'Unknown')}"
    duration_text = f"{_metric(command.get('estimated_duration'))} minutes"
    confidence_text = f"{_metric(command.get('confidence_score'))}%"

    st.markdown(
        f"""
        <div class="dc-mission">
            <div class="dc-kicker">Today's Mission</div>
            <div class="dc-mission-title">{_text(command.get('recommended_focus'), 'Upper Body Strength')}</div>
            <div class="dc-grid" style="margin-top:10px;">
                <div class="dc-chip"><div class="dc-chip-label">Readiness</div><div class="dc-chip-value">{readiness_text}</div></div>
                <div class="dc-chip"><div class="dc-chip-label">Recovery Status</div><div class="dc-chip-value">{_text(command.get('readiness_label'), 'Unknown')}</div></div>
                <div class="dc-chip"><div class="dc-chip-label">Duration</div><div class="dc-chip-value">{duration_text}</div></div>
                <div class="dc-chip"><div class="dc-chip-label">Intensity</div><div class="dc-chip-value">{_text(command.get('intensity'), 'Moderate-Heavy')}</div></div>
                <div class="dc-chip"><div class="dc-chip-label">Weekly Goal Progress</div><div class="dc-chip-value">{_text((weekly.get('strength', {}) or {}).get('label'), 'Not available')}</div></div>
                <div class="dc-chip"><div class="dc-chip-label">Confidence</div><div class="dc-chip-value">{confidence_text}</div></div>
            </div>
            <div style="margin-top:10px;color:#cfe4ff;">Reason: {_text(command.get('main_reason'), 'Recommendation based on readiness and recent workload.')}</div>
            <div style="margin-top:6px;color:#93c5fd;">Cardio Add-on: {_metric(cardio.get('duration_minutes'))} min {_text(cardio.get('activity_type'), 'Not available')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    a1, a2, a3, a4 = st.columns(4)
    action = ''
    if a1.button("Start Today's Workout", width='stretch'):
        action = 'start_workout'
    if a2.button('Preview Workout', width='stretch'):
        action = 'preview_workout'
    if a3.button('Adjust Plan', width='stretch'):
        action = 'adjust_plan'
    if a4.button('Recovery Instead', width='stretch'):
        action = 'recovery_instead'

    st.markdown('### Daily Snapshot')
    snapshot_cards = [
        ('Apple Activity', _metric(snapshot.get('apple_activity_status'))),
        ('Steps', _metric(snapshot.get('steps'))),
        ('Exercise Minutes', _metric(snapshot.get('exercise_minutes'))),
        ('Sleep', _metric(snapshot.get('sleep_hours'))),
        ('HRV', _metric(snapshot.get('hrv_ms'))),
        ('Resting Heart Rate', _metric(snapshot.get('resting_hr_bpm'))),
        ('Weekly Workouts', _metric(snapshot.get('weekly_workouts'))),
        ('Weekly Cardio', _metric(snapshot.get('weekly_cardio_minutes'))),
        ('Latest PR', _metric(snapshot.get('latest_pr'))),
        ('Current Body Weight', _metric(snapshot.get('body_weight_lbs'))),
    ]
    snapshot_html = ''.join([
        f'<div class="dc-s-card"><div class="dc-s-label">{label}</div><div class="dc-s-value">{value}</div></div>'
        for label, value in snapshot_cards
    ])
    st.markdown(f'<div class="dc-snapshot">{snapshot_html}</div>', unsafe_allow_html=True)

    st.markdown('### Weekly Mission')
    strength = weekly.get('strength', {}) if isinstance(weekly.get('strength'), dict) else {}
    cardio_week = weekly.get('cardio_minutes', {}) if isinstance(weekly.get('cardio_minutes'), dict) else {}

    weekly_rows = [
        ('Strength', _metric(strength.get('current')), _metric(strength.get('target')), f"{_metric(strength.get('current'))} of {_metric(strength.get('target'))}"),
        ('Cardio', _metric(cardio_week.get('current')), _metric(cardio_week.get('target')), f"{_metric(cardio_week.get('current'))} of {_metric(cardio_week.get('target'))} min"),
        ('Pickleball', _metric(weekly_ext.get('pickleball_sessions')), _metric(weekly_ext.get('pickleball_target')), _ratio_label(weekly_ext.get('pickleball_sessions'), weekly_ext.get('pickleball_target'), 'sessions')),
        ('Steps', _metric(weekly_ext.get('step_total')), _metric(weekly_ext.get('step_goal')), _ratio_label(weekly_ext.get('step_total'), weekly_ext.get('step_goal'))),
        ('Recovery Days', _metric(weekly_ext.get('recovery_days')), _metric(weekly_ext.get('recovery_target')), _ratio_label(weekly_ext.get('recovery_days'), weekly_ext.get('recovery_target'), 'days')),
        ('Workout Streak', _metric(weekly_ext.get('workout_streak')), _metric(weekly_ext.get('streak_target')), _ratio_label(weekly_ext.get('workout_streak'), weekly_ext.get('streak_target'), 'days')),
    ]

    for label, current, target, value_text in weekly_rows:
        pct = 0
        try:
            if current != 'Not available' and target != 'Not available':
                pct = min(100, int((float(current) / max(1.0, float(target))) * 100))
        except Exception:
            pct = 0
        st.markdown(
            f'<div class="dc-w-row"><div class="dc-w-label">{label}</div><div class="dc-w-bar"><div class="dc-w-fill" style="width:{pct}%;"></div></div><div class="dc-w-value">{value_text if value_text.strip() else "Not available"}</div></div>',
            unsafe_allow_html=True,
        )

    alerts = command.get('alerts', []) if isinstance(command.get('alerts'), list) else []
    for note in alerts:
        st.warning(str(note))

    if health.get('missing_data'):
        st.info('Import an Apple Health export to unlock activity and recovery insights.')

    st.markdown('</div>', unsafe_allow_html=True)
    return action
