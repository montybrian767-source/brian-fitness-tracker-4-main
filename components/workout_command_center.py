from __future__ import annotations

from typing import Any

import streamlit as st

from components.exercise_intelligence_panel import exercise_intelligence_panel


def _text(value: Any, default: str = '-') -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _rating(score: float) -> str:
    if score >= 90:
        return '★★★★★ Perfect Match'
    if score >= 75:
        return '★★★★ Very Good'
    if score >= 60:
        return '★★★ Good'
    return '★★ Fair'


def workout_command_center(
    row,
    idx,
    total,
    photo_html,
    last_weight,
    last_reps,
    best_weight,
    sets,
    reps_default,
    ai_cue,
    completed_today,
    total_volume_today,
    day,
    exercise_data=None,
    key_prefix="wcc",
    disable_actions=False,
):
    """Render a premium Workout Command Center with Exercise Intelligence integration."""
    rest_context = st.session_state.get(f'{key_prefix}_rest_context', {})
    if not isinstance(rest_context, dict):
        rest_context = {}
    live_feedback = st.session_state.get(f'{key_prefix}_last_execution_feedback', {})
    if not isinstance(live_feedback, dict):
        live_feedback = {}
    pr_burst = st.session_state.get(f'{key_prefix}_recent_pr_burst', {})
    if not isinstance(pr_burst, dict):
        pr_burst = {}

    row_dict = row if isinstance(row, dict) else row.to_dict()
    exercise_name = _text(row_dict.get('exercise', ''))
    total_sets_target = max(1, int(_num(row_dict.get('target_sets', 1), 1)))
    current_set = min(max(1, int(_num(completed_today, 0)) + 1), total_sets_target)
    target_weight = _num(row_dict.get('base_weight', 0), 0.0)
    target_reps_text = _text(row_dict.get('target_reps', '8-12'))
    target_rpe = _text(rest_context.get('target_rpe', '7'))
    rest_seconds = int(_num(rest_context.get('recommended_rest_seconds', 90), 90))
    movement_pattern = _text(exercise_data.get('movement_pattern', 'Unknown'), 'Unknown') if isinstance(exercise_data, dict) else 'Unknown'
    primary_muscle = _text(exercise_data.get('primary', exercise_data.get('muscle_group', 'General')), 'General') if isinstance(exercise_data, dict) else 'General'
    secondary_muscles = exercise_data.get('secondary_muscles', []) if isinstance(exercise_data, dict) else []
    if isinstance(secondary_muscles, str):
        secondary_muscles = [item.strip() for item in secondary_muscles.split(',') if item.strip()]

    left, right = st.columns([1.05, 0.95])

    with left:
        st.markdown(
            f'''
            <div style="position:sticky;top:110px;z-index:994;background:linear-gradient(145deg,#071423,#112b49);border:1px solid #2b5f93;border-radius:18px;padding:14px 16px;margin:0 0 12px 0;box-shadow:0 10px 22px rgba(0,0,0,.28);">
              <div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:flex-end;">
                <div>
                  <div style="font-size:.78rem;font-weight:900;letter-spacing:.14em;color:#7dd3fc;">Current Exercise</div>
                  <div style="font-size:1.35rem;font-weight:950;color:#f8fafc;margin-top:2px;">{exercise_name}</div>
                </div>
                <div style="font-size:.82rem;color:#bfdbfe;font-weight:800;">Exercise {int(idx) + 1} of {int(total)}</div>
              </div>
              <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px;">
                <div style="background:rgba(15,31,52,.9);border:1px solid rgba(96,165,250,.22);border-radius:14px;padding:10px;">
                                    <div style="font-size:.72rem;color:#93c5fd;font-weight:900;text-transform:uppercase;">Set</div>
                                    <div style="font-size:1.35rem;color:#fff;font-weight:950;">Set {current_set} of {total_sets_target}</div>
                </div>
                <div style="background:rgba(15,31,52,.9);border:1px solid rgba(96,165,250,.22);border-radius:14px;padding:10px;">
                  <div style="font-size:.72rem;color:#93c5fd;font-weight:900;text-transform:uppercase;">Target</div>
                                    <div style="font-size:1.05rem;color:#fff;font-weight:950;">{target_weight:.0f} lb</div>
                  <div style="color:#c8d3e6;font-weight:800;">{target_reps_text} reps</div>
                </div>
                <div style="background:rgba(15,31,52,.9);border:1px solid rgba(96,165,250,.22);border-radius:14px;padding:10px;">
                  <div style="font-size:.72rem;color:#93c5fd;font-weight:900;text-transform:uppercase;">Target RPE</div>
                  <div style="font-size:1.1rem;color:#fff;font-weight:950;">{target_rpe}</div>
                </div>
                <div style="background:rgba(15,31,52,.9);border:1px solid rgba(96,165,250,.22);border-radius:14px;padding:10px;">
                                    <div style="font-size:.72rem;color:#93c5fd;font-weight:900;text-transform:uppercase;">Rest</div>
                  <div style="font-size:1.1rem;color:#fff;font-weight:950;">{rest_seconds} sec</div>
                </div>
              </div>
              <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;">
                <span class="badge green">{_text(row_dict.get('muscle_group', 'General'))}</span>
                <span class="badge">{movement_pattern}</span>
                                <span class="badge">Primary {primary_muscle}</span>
                <span class="badge">{_rating(_num(live_feedback.get('confidence', 0), 0))}</span>
              </div>
            </div>
            ''',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div style="border-radius:16px;overflow:hidden;background:#0f1f34;padding:8px;cursor:zoom-in;" title="Tap to enlarge">{photo_html}</div>',
            unsafe_allow_html=True,
        )

        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(
                f'<div style="background:#07111f;border-radius:10px;padding:10px;text-align:center;">'
                f'<div style="color:#93c5fd;font-size:.75rem;font-weight:900;text-transform:uppercase;">Last Workout</div>'
                f'<div style="font-weight:900;font-size:1.15rem;">{last_weight:g} x {int(last_reps or 0)}</div></div>',
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                f'<div style="background:#07111f;border-radius:10px;padding:10px;text-align:center;">'
                f'<div style="color:#93c5fd;font-size:.75rem;font-weight:900;text-transform:uppercase;">Current PR</div>'
                f'<div style="font-weight:900;font-size:1.15rem;">{best_weight:g} lbs</div></div>',
                unsafe_allow_html=True,
            )
        with m3:
            coach_weight = _text(live_feedback.get('suggestion', ''), _text(live_feedback.get('coach_recommendation', '100 x 12 today')))
            st.markdown(
                f'<div style="background:#07111f;border-radius:10px;padding:10px;text-align:center;">'
                f'<div style="color:#93c5fd;font-size:.75rem;font-weight:900;text-transform:uppercase;">Coach Recommendation</div>'
                f'<div style="font-weight:900;font-size:1.02rem;">{coach_weight}</div></div>',
                unsafe_allow_html=True,
            )

    with right:
        if exercise_data:
            exercise_intelligence_panel(exercise_data)

        if live_feedback:
            st.markdown(
                f'''
                <div style="background:linear-gradient(145deg,#0a1829,#102845);border:1px solid rgba(34,197,94,.35);border-radius:16px;padding:14px;margin-top:12px;">
                  <div style="font-size:.78rem;font-weight:900;letter-spacing:.14em;color:#86efac;text-transform:uppercase;">Coach</div>
                  <div style="font-size:1.15rem;color:#fff;font-weight:900;margin-top:4px;">{_text(live_feedback.get('coach_line', live_feedback.get('suggestion', 'Excellent tempo.')))}</div>
                  <div style="color:#c8d3e6;margin-top:6px;">{_text(live_feedback.get('comparison', ''))}</div>
                </div>
                ''',
                unsafe_allow_html=True,
            )

        if pr_burst:
            st.markdown(
                f'''
                <div style="background:linear-gradient(135deg,rgba(245,158,11,.18),rgba(15,31,52,.95));border:1px solid rgba(245,158,11,.55);border-radius:16px;padding:14px;margin-top:12px;">
                  <div style="font-size:.78rem;font-weight:900;letter-spacing:.14em;color:#fcd34d;text-transform:uppercase;">New PR</div>
                  <div style="font-size:1.05rem;color:#fff;font-weight:900;margin-top:4px;">{_text(pr_burst.get('headline', 'New personal best!'))}</div>
                  <div style="color:#fef3c7;margin-top:6px;">{_text(pr_burst.get('detail', ''))}</div>
                </div>
                ''',
                unsafe_allow_html=True,
            )

    st.markdown('### Log This Set')
    col1, col2, col3 = st.columns(3)
    with col1:
        weight = st.number_input('Actual Weight', min_value=0.0, value=float(last_weight or row_dict.get('base_weight', 0)), step=2.5, key=f'{key_prefix}_w_{idx}')
    with col2:
        reps = st.number_input('Actual Reps', min_value=0, value=int(reps_default or 8), step=1, key=f'{key_prefix}_r_{idx}')
    with col3:
        rpe = st.number_input('Actual RPE', min_value=0.0, max_value=10.0, value=7.0, step=0.5, key=f'{key_prefix}_rpe_{idx}')

    body_feedback_score = st.slider('Body Check-In', 0, 10, 0, key=f'{key_prefix}_body_feedback_{idx}')
    set_number = st.number_input('Set number', min_value=1, max_value=max(int(sets or 8), 8), value=1, step=1, key=f'{key_prefix}_set_{idx}')
    body_feedback_notes = st.text_input('Quick notes', value='', placeholder='Form, difficulty, body check-in, equipment notes...', key=f'{key_prefix}_notes_{idx}')

    vol = int(weight * reps)
    st.markdown(f'<div style="background:#07111f;border-radius:12px;padding:12px;margin-bottom:12px;"><div style="color:#93c5fd;font-size:.85rem;">Current Set Volume</div><div style="font-size:1.8rem;font-weight:900;color:#22c55e;">{vol:,} lbs</div></div>', unsafe_allow_html=True)

    complete = st.button('Complete Set', key=f'{key_prefix}_complete_{idx}', width='stretch', disabled=bool(disable_actions), type='primary')

    nav1, nav2, nav3, nav4 = st.columns(4)
    with nav1:
        prev_clicked = st.button('Previous Exercise', key=f'{key_prefix}_prev_{idx}', disabled=(idx <= 0), width='stretch')
    with nav2:
        next_clicked = st.button('Next Exercise', key=f'{key_prefix}_next_{idx}', disabled=(idx >= total - 1), width='stretch')
    with nav3:
        st.caption(f'Exercise {idx + 1} of {total}')
    with nav4:
        finish_clicked = st.button('Finish Workout', key=f'{key_prefix}_finish_{idx}', width='stretch', disabled=bool(disable_actions))

    st.markdown(f'**Progress:** {completed_today} sets logged • {total_volume_today:,} lbs')
    progress_pct = 0
    try:
        progress_pct = min(100, int((completed_today / max(1, int(row_dict.get('target_sets', 1)))) * 100))
    except Exception:
        progress_pct = 0
    st.progress(progress_pct / 100.0)

    timeline = [
        ('Warmup', 'current' if int(idx) == 0 else 'done'),
        (f'Exercise {int(idx) + 1}', 'current'),
        ('Cardio', 'future'),
        ('Cooldown', 'future'),
    ]
    timeline_html = ''.join(
        [
            f'<div style="padding:10px;border-radius:12px;border:1px solid {'rgba(34,197,94,.4)' if status == 'done' else 'rgba(96,165,250,.5)' if status == 'current' else 'rgba(148,163,184,.18)'};background:{'rgba(34,197,94,.08)' if status == 'done' else 'rgba(37,99,235,.18)' if status == 'current' else 'rgba(15,23,42,.65)'};color:#fff;font-weight:900;">{name}</div>'
            for name, status in timeline
        ]
    )
    st.markdown(f'<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px;">{timeline_html}</div>', unsafe_allow_html=True)

    return {
        'complete': complete,
        'weight': weight,
        'reps': reps,
        'rpe': rpe,
        'pain': body_feedback_score,
        'body_feedback_score': body_feedback_score,
        'set_number': set_number,
        'notes': body_feedback_notes,
        'body_feedback_notes': body_feedback_notes,
        'volume': vol,
        'prev': prev_clicked,
        'next': next_clicked,
        'finish': finish_clicked,
    }
